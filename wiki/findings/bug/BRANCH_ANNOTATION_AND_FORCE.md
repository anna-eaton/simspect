# Branch annotations: loader bug confirmed, the BTB force was wrong, and resolved branches were not guaranteed correct (2026-10-30)

For Anna, top to bottom. Verdict: **harness/hook bugs, not gem5 defense bugs.** Every campaign before 2026-10-30 ran with at least one of them. All are fixed and verified on all 8 hooked builds. The old results are being zipped (§6).

## 1. Claims

1. **gem5-spt and gem5-recon-modded never loaded a single branch annotation in mainline runs** (the 2026-10-29 finding you doubted). Proven below by running the same tests with the exact annotation file the old harness handed gem5, and looking at what gem5 instantiated and what the pipeline did.
2. **The old BTB force ("predict taken to the pc+1 label") was wrong on every build that honored it.** On gem5-22 builds (SpecLFB; recon-modded once the alias was added) decode caught the forced branch and squashed it there, so it never mispredicted at execute: no resolve stall, no speculation window. On old-gem5 builds the forced fetch landed on the label, which can sit past instructions LLVM hoisted into the block (e.g. a `lea` that sets the base register). The wrong path then ran a slightly different program from the one the model describes.
3. **Not-taken modes and resolved branches relied on the cold predictor guessing "not taken".** Wherever LLVM put the next Alloy instruction on the x86 taken side, that guess was wrong. An unresolved branch was then predicted correctly (no window), or a resolved branch mispredicted (an extra window the model doesn't have).
4. **In sweep runs, resolved branches with a grid stall were treated as "must still be unresolved" at the leak**, which is the reverse of what the model says (`gem5_common.collect_unresolved_branches` took every entry with stall > 0).
5. **The resolve-stall hook itself (pre-existing, all 8 builds) never woke the CPU.** When a branch was held long enough for the ROB to fill and the CPU to go idle, the release either reached commit late (27–40 cycles in 28 of 331 audited instances) or never did. In that case gem5 ran to `--abs-max-tick` with the program frozen (stt inst-000733 mispredict_taken: 1,213 CPU cycles simulated, then nothing until tick 1e11). Every campaign with the 5000-cycle unresolved stall contains such runs; they could only ever be non-hits (false negatives).

## 2. Evidence (all re-runnable)

Harness: `STAGE3_gem5/hook_audit.py` (design: `wiki/design/RESOLUTION_HOOKS.md` §4). 6 STT_6 tests per mode × 8 builds, S = 200-cycle resolve stall, F = 150-cycle fnc stall. Results: `wiki/findings/audits/2026-10-30/hook_audit_pre_rebuild_sha.json` (before the rebuild) and `hook_audit_post_rebuild_all.json`.

**Claim 1 (loader).** Variant `raw_S` hands gem5 the .ann.json exactly as compile_annotate writes it (`branch_addr` only), with the unresolved stall S.

| build | branches in config.ini `annotationBranchPCs` (raw file) | squash shift from the stall (raw file) | raw trace == aliased trace |
|---|---|---|---|
| gem5-spt | **0 of all, 12/12 tests** (`got: []`) | **0.0 cycles, 12/12** | no, 12/12 |
| gem5-recon-modded | **0, 12/12** | **0.0 cycles, 6/6 measurable** | no, 12/12 |
| stt, stt-dbg, amulet InvisiSpec/CleanupSpec/SpecLFB/STT | all, 12/12 (CleanupSpec 8/8 that ran) | 200 cycles | yes, identical |

Same tests, same binaries. Only the key name differs. Mechanism: `/work/gem5-spt/configs/example/se.py:63-66` and `/work/gem5-recon-modded/configs/example/se.py:110-115` read only `branch_pc_addr[_hex]` or x86 offsets (recon-modded warns `annotation missing branch PC, skipping` and drops the entry). The alias added in `gem5_common._branch_ann_for_se` fixes it (`registered_ann` PASS 12/12 on both).

**Claim 2 (force on gem5-22).** recon-modded, inst-031193 mispredict_taken (Branch,Fetch,Commit trace, aliased annotation): `Annotation override: forcing BTB target at PC 0x401c5c to 0x401c5e`, then at 2677500 `Squashing from decode with PC = (0x401c79=>...)`. There is no `Squashing due to branch mispred` at execute. Without the force the same branch mispredicts at execute (commit squash at 2679500). Audit `force_taken`: recon-modded and SpecLFB FAIL 6/6 (force removes the execute-stage mispredict). The old-gem5 builds still mispredict at execute. The disassembly shows why: in taken mode the condition is a constant and `je` jumps to the `ftbypass` trampoline, so the critical section is the x86 fall-through. The forced target is the `pc+1` label: delta from the jcc was 7 bytes in 3761 / 5000 STT_6 taken-mode branches, 2 in 889, 10 in 188, 5 in 116. A 2-byte jcc means the label skips 0, 3 or 5 bytes of hoisted code (inst-000002: `lea -0x18(%rsp),%rdi` at 0x40105a sits before label pc2 at 0x40105f, so the forced wrong path ran with a stale `%rdi`).

**Claim 3 (natural prediction).** Census of the x86 layout over 1,500 tests per testset/mode (`gem5_common.branch_force_plan`; cafe2 `/tests/claude_hookaudit_20261030/plan_census.json`): branch instances whose next Alloy instruction is on the **taken** side.

| testset / mode | unresolved (mispredict_not_taken) laid out taken = no window under the old harness | resolved laid out taken = resolved branch mispredicted under the old harness |
|---|---|---|
| STT_6 / not_taken | 12 | 8 |
| STT_6 / taken | 0 | 107 |
| STT_6_interleave / not_taken | 99 | 21 |
| STT_6_interleave / taken | 0 | 92 |
| SPT_6_oneLP / not_taken | 36 | 7 |
| SPT_6_oneLP / taken | 0 | 294 |
| Recon_6 / not_taken | 144 | 34 |
| STT_all / not_taken | 6 | 2 |

Checked in gem5 (cafe2 `/tests/claude_hookaudit_20261030/layout_cases.json`). There were 4 Recon_6 tests with a taken-side unresolved branch: on stt, recon-modded and spt, under every old-style variant that branch **never mispredicted** (no window), and under the new force the window opens and the stall works (`plan_0_valid`, `plan_stall_shift` PASS 12/12). There were also 8 SPT_6_oneLP/STT_6 taken-mode tests with a taken-side resolved branch: under every old-style variant **the resolved branch mispredicted** (`resolved_correct` FAIL 24/24), and under the new force it is predicted correctly (`plan_0_valid` PASS 24/24).

**Claim 4 (resolved branches in the window).** Code: `collect_unresolved_branches` (before 2026-10-30) kept any entry with `resolve_stall_cycles > 0`, and `pipeline._inject_stalls` gives resolved branches the sweep grid stall (500, 2500). So at grid points > 0 a leak had to happen before a *resolved* branch resolved. Effect: strictly fewer hits (a stricter gate), never extra ones.

## 3. Fix

- `gem5_common._branch_ann_for_se`: key alias (claim 1), plus the derived force on binaries with the resolve hooks (claims 2-3): force the x86 direction that reaches the next Alloy instruction, as not-taken (target 1, new hook behaviour) or taken to the jcc's own static target. Never force to the label. Rule: `wiki/design/RESOLUTION_HOOKS.md` §2.
- gem5, all 8 hooked builds (backed up, rebuilt 2026-10-30): forced target 1 = predict not-taken, plus print-only BR lines `predict_force`, `resolve_hold/drop/release/bcast`, `resolve_visible`. Diffs: `gem5-hooks/<build>/resolve_hooks.diff`.
- `collect_unresolved_branches` skips resolved entries (claim 4). Resolved-branch timing is reported as `criteria.resolved_before_signal` (not gated).
- Per-record execution validity (`resolved_correct`, `window_opened`, `stall_applied`, `force_applied`): a record that fails any is a `warn`, never a hit. So any future recurrence of claims 1-3 shows up in every result file.

## 4. Verification after the rebuild

- **Print-only:** 546 / 546 audit variant traces (non-simspect pipeview, commit squash ticks, ready-in-ROB ticks) are identical between the pre- and post-rebuild binaries.
- **BR lines agree with gem5's own trace:** `resolve_visible` == the Commit `Marking PC ... ready within ROB` tick for every instance (`br_visible_eq_commit_ready` PASS on all 8 builds). The IEW release is exactly hold + S cycles (`br_hold_release` PASS).
- **Production path:** `plan_0_valid` and `plan_S_valid` PASS on every test that ran on every build. On the gem5-22 builds the force no longer kills the window.
- **Stall placement:** the deferred event holds `setExecuted`, `instToCommit` (and so commit's `setCanCommit`, which is what every defense keys "resolved" on), the squash broadcast and the BPred squash. The independent code review (`wiki/findings/audits/2026-10-30/RESOLVE_HOOKS_CODE_AUDIT.md`) traced each defense's "resolved" signal (STT/SPT `prevBrsResolved`, InvisiSpec/CleanupSpec `readyToExpose`, SpecLFB `updateSafeState`, recon `branchResolved`/ShadowTracker) to `readyToCommit()` after the release: all gated. It also found claim 5. I had first read the 19–40-cycle commit lag as STT's pending-squash path, which was wrong: "can be resolved now" is STT's immediate path, and the lag was the sleeping CPU.
- **Claim 5 fix (wake):** the release now wakes the CPU the way a late memory response does. After the rebuild every audited release→visible gap is exactly 1 cycle (223/223). The frozen test resolves with the stall exactly 5000 cycles. 524 of 536 traces are unchanged and the 12 changed ones are exactly the frozen/late runs.
- **Harness code review** (`wiki/findings/audits/2026-10-30/HARNESS_CODE_AUDIT.md`): it found 3 bugs, all fixed. A reported-only criterion was inside `criteria`. Resumed sweeps overwrote their raw per-record files. hook_audit passed the Alloy xmit pc where the x86 PC was needed. It also raised risks that are now fixed: invalid records counted as errors (now `status="invalid"`), `unknown` plans fell back to the old force (now no force), `_reaches` stopped at `jmp` (now follows it), "oldest branch" by x86 address (now by Alloy pc), and `force_applied` didn't check direction (now does). Remaining, documented: dynamic instances of a re-fetched branch are not paired with the xmit's instance.

## 5. Impact on earlier results (what to distrust)

| campaigns | problem |
|---|---|
| everything on gem5-spt, gem5-recon-modded before 2026-10-30 | no annotation loaded: no forced mispredict, no resolve stall, sweep grid meaningless; check_ld still assumed the stall in `branches_unresolved` |
| mispredict_taken mode on amulet SpecLFB | forced branch squashed at decode: those branches never opened a window |
| mispredict_taken mode on stt, stt-dbg, amulet InvisiSpec/CleanupSpec/STT | forced wrong path started at the label, skipping hoisted instructions (wrong-path program differs from the model) |
| all builds, any mode | taken-side layouts (table in §2): some unresolved branches never mispredicted, some resolved branches did |
| all sweep runs | resolved branches with grid stall > 0 gated as if unresolved (fewer hits) |
| interleaved testsets (STT_6_interleave, STT_all, `_otb_search_*`) | additionally fnc on a chain step in 35–53% (COMMIT_BOUNDARY.md §1) |
| every campaign with the 5000-cycle unresolved stall, all builds | some runs froze (sleeping CPU never woken by the release) and ran to the tick cap; they were silently scored as non-hits |

The STT_6 / recon-modded "STT holds" conclusions and the SPT hit counts should be re-derived from the fixed campaigns (`runconfigs/fixed_20261030/`), not reused.

## 6. Status

- Old `results/` (75 GB, 8.3 M files) is zipped and verified at cafe2 `/tests/simspect/archive/results_pre_resolve_hooks_20261030.zip`. The originals stay until Anna runs `scripts/archive_results_pre_resolve_hooks.sh --delete` (the delete step was blocked for Claude by the permission check, rightly).
- Round 2 (2% samples) finished 2026-10-31 and is classified in §7. It ran on old testset generations (§7.1). Round 4 on `testsets_latest`, with the §7.3 checker fix, started 2026-11-08 01:28 UTC (cafe2 `results/*_fixed_latest__20261108_012818`). The STT_6_interleave regeneration finished but used the old model's XML (§7.1), and the STT_6_commitsplit candidate testset is complete.

## 7. After the fix: every round-2 hit classified, a testset-generation mistake, and a second checker gap (2026-11-07)

### 7.1 Round 2 ran on old testset generations (my mistake)

The 10-30 fixed configs kept `"testset_dir": "testsets"`, the pre-June-3 enumerations. The current models were committed in e298a9e (06-03). They add `rf_from_most_recent_writer`, the `first_uncommitted` fix, and the SPT inaddr de-protect and committed-store leakage. They are enumerated only in `testsets_latest/`. Hashes are from each testset's `provenance.tar.gz` against git history (`STAGE3_gem5/triage/testset_provenance.py`; cafe2 `/tests/simspect_fixed_20261030/triage/testset_provenance.json`).

| testset | .als in provenance | current .als? | parsexml in provenance |
|---|---|---|---|
| `testsets/STT_6` (round 2) | 5cae70e9 (faf0d9a, 05-27) | no | f7cb3a23 (uncommitted, ~05-19) |
| `testsets/SPT_6_oneLP` (round 2) | 5e89267c (14fcb1f, 06-02) | no | 2d7478c8 (uncommitted, 06-01) |
| `testsets/Recon_6` | 12b5ea88 (ec27f02, 05-14) | no | 30de6b77 |
| `testsets_latest/{STT_6,SPT_6_oneLP,Recon_6}` | 7a6ac4c0 / 713d0904 / 01252c82 (e298a9e, 06-03) | **yes** | 30de6b77 (14fcb1f, 06-02) |
| fixed-dir `STT_6_interleave` (my 10-30 regen) | none recorded; reused the 05-19 XML of the old STT_6 model | **no** | 0b4636a6 (10-30) |
| fixed-dir `STT_6_commitsplit` | 3e8dee9d (current, unreviewed) | yes | 0b4636a6 |

`testsets_latest` predates the 10-29 parsexml changes, but for branch-mode, non-interleaved testsets those changes don't alter lc/fnc: `audit_commit_boundary.py` reports 0 offenders on both. The 11-02 parsexml change is STL-only. Round 4 (`runconfigs/fixed_20261030/*_fixed_latest.jsonc`) reruns STT_6/stt, STT_6/recon-modded and SPT_6_oneLP/spt on `testsets_latest`. STT_6_interleave must be regenerated from the current STT_6 XML before its campaign means anything.

### 7.2 Round-2 hits, classified with the per-results classifying scripts

Every hit test went through `diagnostics/bucket_hits.py` in its campaign folder (cafe2 `results/<campaign>__20261030_214301/diagnostics/`, source `STAGE3_gem5/triage/diag/`). That runs the June SPT XML diagnostics, which apply because it's the same testset, plus three new evidence-backed diagnostics. **0 tests are left as NEW.**

| campaign | kind | hit tests (not_taken / taken) | bucket | verdict |
|---|---|---|---|---|
| STT_6 / stt | ld, br_x | 0 / 0 | none | STT holds; the load transmitter never executes |
| STT_6_commitsplit / stt | ld, br_x | 0 / 0 | none | uninformative (STT_6 is also 0 here) |
| STT_6 / recon-modded | ld | 7 / 7 (same 7) | `recon_stlf_bypass` 7 / 7 | **real gem5 bug, known A2**, re-verified on the fixed harness |
| SPT_6_oneLP / spt | ld | 336 / 264 | `constaddr_load` 333 / 262, `rf_clobber` 2 / 1, `nonspec_cotransmit` 1 / 1 | model artifacts (June verdicts) |
| SPT_6_oneLP / spt | br_x | 28 / 22 | `brx_const_condition` 26 / 20, `brx_declassified_condition` 2 / 2 | model / concretization artifacts (new diagnostics) |

**SPT br_x, how it was proven:**
- Every transmitter instance that redirected was fetched inside the primary window and resolved while the older branch was still held, so these are not the old re-fetch artifact.
- An x86 slice of the jcc's flags, using gem5-spt's taint rules (`spt_cond_slice.py`), gives 46 conditions built only from constants and 4 load values declassified by a non-speculative load or store: inst-021589 and inst-043417 in not_taken, inst-013888 and inst-021589 in taken.
- In faithful re-runs at each hit's grid point (`spt_taint_probe.py`) all 50 reproduce, and gem5 never printed "(Lazy) A branch ... made pending" for the transmitter. That is gem5-spt's own verdict that the arguments were untainted (`commit_impl.hh:944`).
- `VPUntaints` is 0 for all 46 constant cases and 1 for all 4 declassified ones.
- Two equal-length counterfactual edits flip the result:
  - inst-043417 with its store's address register changed from `%rax` to `%r12`: `VPUntaints` 0, every transmitter instance made pending, no hit;
  - inst-080310 with its constant source replaced by a load: made pending, no hit.

**SPT ld, cross-check:**
- The same x86 slicer agrees with the June XML verdict on all 600 tests:
  - every `constaddr_load` test slices as constant;
  - every `nonspec_cotransmit` test slices as declassified;
  - the `rf_clobber` tests slice as constant or declassified.
- None slices as tainted.
- 0 of 3,315 hit records got their data at or after the window closed, so the 11-02 concern that the data-obtained gate is not window-bound doesn't touch these hits.

**recon-modded, how it was proven:** I re-ran each of the 7 tests in both modes. In all 14 runs the LSQ prints `STL_CHECK: load PC <xmit> isTainted=1 isSpeculative=1` right after the transmitter executes, then `Forwarding from store idx N to load`. Commit then marks the load ready within the ROB (tick 2,676,000–2,678,000) before the window-opening branch's `resolve_visible` (about 5,173,500). In 4 of the 7 the Alloy shape is load→load. At run time the address still equals an older store's because every value is 0, so the mechanism is the same. This settles the 11-02 doubt that the A2 evidence predated the fix and rested on a grep-filtered trace.

### 7.3 Second checker gap: lc/fnc missing from O3PipeView (fixed)

gem5 prints an O3PipeView record from the DynInst destructor (`dyn_inst_impl.hh:73`). gem5-spt kept some committed stores alive to the end of the run, so they never got one. Example: inst-043417's fnc store commits at 2,952,000 per the Commit trace, with no record. The checkers then read `fnc_retire = 0`, which makes `before_fnc` pass vacuously, or `lc_retire = 0`, which disqualifies through `lc_retired`.

- **Fix:** `gem5_common.process_one` now fills a missing lc/fnc retire from the Commit trace's first `Committing instruction` tick (`parse_commit_ticks` + `fill_retire_from_commit`; flagged in `retire_from_commit_trace`). Where both exist they agree on 273/282 instructions and differ by exactly one cycle on the other 9.
- **Effect on round 2, all SPT:**
  - 33 of the 91 hit records with a vacuous fnc had fnc commit before the signal. That's 3 tests (inst-034362, inst-038197, inst-094716), so those records were false hits.
  - The 126 records that failed only `lc_retired` (30 tests) were re-run: 120 now fail `after_lc` and 6 become hits (2 tests), both `rf_clobber`.
- So the gap added a few false hits and hid no new ones. Round 4 runs with the fix. The recon traces showed no missing records; stt and the amulet builds aren't checked yet.

### 7.4 Not understood yet

1. Why gem5-spt keeps committed stores' DynInsts alive to the end of the run. The effect is handled by 7.3, but I haven't traced the cause.
2. inst-043417's transmitter branch is re-fetched and re-mispredicts about every 15 cycles while the window is open (seq 565, 603, 641, ...). Only the first instance is scored. The re-fetch path isn't traced; it's likely a wrong-path `retq` returning into the function.
3. `resolved_before_signal` is False in every hit record of 450 / 600 SPT ld tests and 32 / 50 br_x tests, and 3 of 14 recon test×mode pairs.
   - Many of the late branches are younger than the transmitter or on the wrong path, where resolving after the signal is natural.
   - Some are held by the sweep grid's resolved-branch stall: inst-080310 hits only at grid points 1–2, because its fnc is a resolved branch and the stall delays fnc's commit.
   - The criterion as written counts younger resolved branches too, which may be the wrong rule. That belongs to the pending DECIDE.
4. gem5-spt `--trackInstsFile` aborts on the first 64-bit register (`regfile.hh:280` asserts `size + offs < taintVec.size()`, an off-by-one in the logging helper). SPT's own per-instruction taint log can't be used without a gem5 patch, so 7.2 uses the "made pending" lines and stats instead.

### 7.5 Tools (`STAGE3_gem5/triage/`, run in the container from the fixed repo copy)

- `hit_facts.py`: per-hit-record window and branch-instance facts.
- `spt_cond_slice.py`: x86 slice with gem5-spt's taint rules.
- `spt_taint_probe.py`: faithful re-run at a grid point, collecting pending lines and SPT stats; `--keep` keeps the trace.
- `run_spt_brx_triage.sh`: runs the three above for a campaign.
- `fnc_commit_check.py`: re-derives fnc commit ticks.
- `testset_provenance.py`: provenance hashes.
- `diag/`: the diagnostics and the multi-kind `bucket_hits.py`.

Outputs are in cafe2 `/tests/simspect_fixed_20261030/triage/`.

### 7.6 Round 4: current models, fixed checker (2026-11-08)

Campaigns are cafe2 `results/*_fixed_latest__20261108_012818` (2% of `testsets_latest`). Analyses are in `/tests/simspect_fixed_20261030/triage/r4/`.

| campaign | hit tests (not_taken / taken) | classification |
|---|---|---|
| STT_6 / stt | 0 / 0 | STT holds |
| STT_6 / recon-modded, ld | 91 / 94 | all 185 = real bug A2 (store-forwarding bypass of the STT check), `recon_stlf_check.py` |
| SPT_6_oneLP / spt, ld | 57 / 48 | x86 slice: 87 constant, 18 declassified |
| SPT_6_oneLP / spt, str | 74 / 60 | 95 constant, 39 declassified; no store checker yet |
| SPT_6_oneLP / spt, br_x | 51 / 51 | 73 constant, 29 declassified; gem5 never delayed the branch (102/102 reproduced) |

Every SPT hit's transmitter operand is public under SPT's rules. The causes are in the model (missing `rf_from_most_recent_writer`, one-step propagation lag) and in concretization (unfed reads). Plan: `wiki/state/ALLOY_MODEL_CHANGES.md` (2026-11-08). Round-4 `diagnostics/` folders are not deployed yet: the June SPT XML diagnostics are testset-specific, and ld/str need slicer-based diagnostics.
