# Commit boundary (lc / fnc), branch annotations, and what the harness enforces

Design decisions made 2026-10-29 with Anna. This page is the audit reference: each rule says where it lives in code and how to check it.

## 1. lc and fnc are pinned to Alloy instructions (rule)

**Rule.** `last_committed` (lc) and `first_noncommitted` (fnc) are always instructions from the Alloy instance, never synthetic ones. Synthetic records are the `pass_interleave` chain steps (`_chainK_stepJ`) and the `_xm_fallthrough_nop`; both carry `"synthetic": True`.

**Where.** One function chooses them: `STAGE2_compilation/parsexml.py:commit_boundary`. Both consumers call it: `pass5_emit_llvm` (the `__litmus_<stem>_last_committed` / `_first_noncommitted` labels) and `emit_branch_annotations` (`ann["commit_boundary"]`). The label and the annotation therefore cannot disagree. Do not add a second boundary computation anywhere.

**Why.** Before the fix both places took "last committed / first uncommitted record" from the post-interleave list. `pass_interleave` inserts chain steps anywhere after the committed prefix, including the slot right after lc, so a chain step became fnc. That put the fnc commit-stall hook and the checker's `fnc_retire` window edge on a synthetic, correct-path instruction. Measured: 624 / 1600 (39%) of locally regenerated STT_6 interleave variants, 2838 / 8000 of cafe2 `testsets/_otb_search_c1`, 4264 / 8000 of `testsets/_otb_search_c2`. lc was never affected (nothing is inserted before it).

**Verified.** Non-interleaved output is byte-identical before/after on 200 STT_6 instances × 2 modes. Interleaved: only the 624 bad boundaries changed, every other ann field and every `.ll` line other than the two boundary labels is identical, and all 1600 variants now carry the same lc/fnc atoms as their base instance.

**Provenance kept.** `compile_annotate.py` used to delete the `atom` field from `commit_boundary` entries and from `xmit`; it now keeps them, so a resolved `.ann.json` says which instruction its boundary is.

## 2. Audit

```bash
python3 STAGE2_compilation/audit_commit_boundary.py testsets/<model>      # exit 1 if any lc/fnc is synthetic
```

Works on old testsets too: when `atom` is missing it recovers it from the `.ll`'s `; pc=N  <atom>  (...)` comments. Any testset generated with interleave before 2026-10-29 fails this audit and must be regenerated from the llvm stage (`--force` on `llvm`, then `asm`); results run on those testsets used the wrong fnc for ~35-53% of tests.

## 3. Branch annotations must be readable by every build's se.py (rule)

**Rule.** The `--branch-ann-file` handed to gem5 carries each branch's absolute PC under both `branch_addr[_hex]` and `branch_pc_addr[_hex]`.

**Where.** `STAGE3_gem5/gem5_common.py:_branch_ann_for_se`, called from `run_gem5`, writes `branch_ann_se.json` in the test's workdir. This is the only place an annotation is handed to gem5, so existing testsets need no regeneration.

**Why.** `compile_annotate.py` writes `branch_addr[_hex]` (what `/work/stt` and the amulet builds read). The `/work/gem5-spt` (`configs/example/se.py:63-66`) and `/work/gem5-recon-modded` (`se.py:110-115`) loaders only accept `branch_pc_addr[_hex]` or x86 offsets and skip every other entry. Checked 2026-10-29: SPT's loader took 0 of 503 annotations from 200 real SPT_6_oneLP files, recon-modded's 0 of 414 (warning `annotation missing branch PC, skipping` each time), stt's 414 of 414; a real `gem5-spt` run left `annotationBranchPCs=` empty in `config.ini`, and adding the alias made it `annotationBranchPCs=4201542 … annotationResolveStallCycles=5000`. **So every mainline campaign on gem5-spt and gem5-recon-modded ran with no BTB force and no resolve stall,** while `check_ld` still assumed the stall when it computed `branches_unresolved` (`complete + stall × ticks/cycle`). The bugsynth fork had fixed this in its own `compile_annotate.py` on 2026-06-08 (claudelog) but it never reached mainline. The fix is not on cafe2 until `make sync`.

## 4. Stable seeds (rule)

**Rule.** Every per-test random seed comes from `zlib.crc32(<name>)`, never from Python's `hash()`, which is salted per process (cafe2 has no `PYTHONHASHSEED`; two runs gave different `hash("inst-000001_v0")`).

**Where.** `STAGE2_compilation/batch_generate.py` (per-variant seed: pass2 instruction choice and pass_interleave chains) and `pipeline.py` (sweep grid subsampling), plus the same lines in `bugsynth/`. Before the fix a regenerated testset had different concrete programs under the same stem names, and a sweep's grid subsample differed run to run. Verified: two generations with different hash salts are now byte-identical. Seeds changed with the fix, so new generations differ from existing testsets by design (those were not reproducible anyway).

## 5. The commit split (STT_6_commitsplit.als)

`STAGE1_alloy/models/STT_6_commitsplit.als` is a copy of STT_6 (which is untouched) with three changes, written for Anna on 2026-10-29 and **awaiting her clause-by-clause review**:

- **C / D / U.** `iscommitted` (C) is the must-be-committed prefix; a new `isuncommitted` (U) is the must-still-be-uncommitted suffix and contains every unresolved instruction (an unresolved instruction can never have committed); D is the don't-care middle where the real commit head may sit. New perturbation `RU` un-commits.
- **Leak at every commit-head position, laxest boundary.** (L) the leak holds with only C committed and for every cut that also commits a prefix of D. (MC) un-committing lc secures (so C can't shrink). (MU) also committing fnc secures, unless fnc is unresolved (so U can't shrink).
- **Every unresolved instruction necessary.** (N) `all i: unresolved | not secure[RR->(unresolved - i)]`: each unresolved instruction on its own sustains the leak (`MINIMALITY_TAGALONG_FIX.md` §3.1 variant 2). This replaces STT_6's per-branch clause (b), which effectively allowed only one unresolved branch, and the commit+resolve clause (c). Unresolved branches need not be contiguous.

**First 200 instances (scope unchanged, 4 s):** C is always empty and fnc is always the first unresolved branch, with everything before it in D. That is what the model's semantics predict: STT untaints by resolution (`STT_6.als:331`), so commit is not load-bearing and the laxest boundary commits nothing. 48 / 200 have 2-3 unresolved branches (14 non-contiguous); no unresolved non-branch survives. All 200 concretize in both modes, with interleave too. The split will matter for defenses whose model does depend on commit.

**Parser support.** `parsexml.py` reads `isuncommitted` into `rec["must_uncommitted"]`; `commit_boundary` takes fnc = first Alloy record of U. For models without the field, U = every uncommitted instruction, so their output is unchanged (verified: identical boundaries on 400 STT_6 programs).

## 6. What the checker reports (snapshot for re-analysis)

`check_ld` now writes `criteria` per record, each criterion as its own pass/fail: `lc_retired`, `signal_seen`, `after_lc`, `before_fnc`, `branches_unresolved`, `data_obtained` (None when the LSQ gate does not apply). `issued_in_window` = all non-None criteria. A near-miss (exactly one false) reads straight out of `window-results.json` without re-running gem5. `check_br`, `check_other` and `check_footprint` do not yet have this; see `wiki/findings/mdsToRead/NEAR_MISS_BREAKDOWN.md` for the breakdown of existing campaigns.

## 7. Enforcement plan (decided, not yet built)

- **The window is "the targeted branches are still unresolved", measured, not estimated.** Today `branches_unresolved` is `pipeview complete + stall × ticks/cycle`, which only holds if gem5 actually registered the stall (§3). Plan: print-only `O3PipeView:simspect:<tick>:BR:` lines (`resolve_hold`, `resolve_release`, `resolve_visible`) in each hooked build, parsed into per-branch ticks per record; a missing hold line for a stalled branch becomes an error. Build inventory, release points and per-build feasibility: [`RESOLUTION_HOOKS_SURVEY.md`](RESOLUTION_HOOKS_SURVEY.md). Needs Anna's OK to edit and rebuild the hook code.
- **lc stays a hard condition** (`after_lc`, `lc_retired`): a transmitter firing before lc retires is a different execution from the one modeled.
- **fnc commit stall off** once the window is resolution-based (it widened the window without adding speculation: claudelog 2026-06-03 05:00).
- **Resolved branches.** Not checked by the harness. A branch the model calls resolved either is correctly predicted (no window of its own; nothing to enforce) or is on the wrong path of an older unresolved branch (squashed anyway). The `resolve_visible` lines will show it for free; a dedicated check is only worth adding if that data shows a resolved branch mattering.

## 8. Copies of the parse scripts (canonical = `STAGE2_compilation/`)

| Copy | What it is for | Status after 2026-10-29 |
|---|---|---|
| `STAGE2_compilation/{parsexml,batch_generate,compile_annotate}.py` | the pipeline (`pipeline.py`, `testsetgen.py`, dashboard) | canonical; all fixes above |
| `bugsynth/STAGE2_compilation/` + `bugsynth/pipeline.py` | isolated fork from the 2026-06-08 bugsynth session that reproduced the OTB and pending-squash bugs (`bugsynth/WALKTHROUGH.md`); 514 diff lines vs mainline (tainted-branch routing, its own models) | lc/fnc fix and stable seeds applied; already had the §3 alias. Its own models/routing were never folded into mainline (owner decision from 2026-06-08, still open) |
| `oldest_taint_bug/{parsexml,compile_annotate}_patched.py` | frozen one-off repro of the recon OTB bug (`oldest_taint_bug/run.py`); no interleave | left as is: the bug cannot occur there (no chain steps), and editing it would change a frozen repro |
| `old/{parsexml,xml2llvm,xml2x86}.py` | pre-pipeline prototypes, nothing imports them | left as is; candidates to delete (Anna's call) |
| `gem5-hooks/verify/mkann.py` | hand-written ann for hook verification | no boundary computation; nothing to fix |
