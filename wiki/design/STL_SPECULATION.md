# Store-to-load (STL) speculation: model, concretization, gem5 hooks, window check

*Living doc, overwrite-in-place. Written 2026-10-28, updated 2026-10-30 (hooks built + tested) and 2026-11-08 (STL for every main model; manifest handoff). This is the one place for everything known about STL in SimSpect. Paper table row: [`SPEC_PRIMITIVE_INSTANCES.md`](SPEC_PRIMITIVE_INSTANCES.md) (h, i).*

## Manifest handoff (2026-11-08): the active STL builds, models and experiments

**Consolidated 2026-11-08 into [`../state/EVAL_MANIFEST.md`](../state/EVAL_MANIFEST.md)** (eval rows, two-stage families incl. the STL cores, STL per defense). This section stays as the STL detail and evidence; when STL status changes, update the manifest and `specs/defense_units.json` too.

For the agent writing the manifest of active builds, models and experiments. Everything below is current as of 2026-11-08 14:40 PST; sections further down hold the evidence. "Draft" = unapproved, in `STAGE1_alloy/models/proposed/` or `proposed_twophase/`, which the pipeline does not read.

**What STL is here.** Store-to-load speculation: an older store's address is held unresolved, the memory-dependence predictor is forced to say "no alias", a younger load to the same address reads the stale value, and the store's address resolution squashes it (memory-order violation). The window is load issue → that squash. Spectre v4. The other direction (predict alias, addresses differ) opens no window in gem5 and is only a negative control.

### Builds

| Build | STL hooks? | Status | Notes |
|---|---|---|---|
| `/work/gem5-recon-stl` (cafe2) | **yes, the only one** | active, but **stale** | Copy of `gem5-recon-modded` taken before the 2026-10-30 resolve hooks: no BR lines, old-style branch force, no CPU-wake fix (`wiki/findings/audits/2026-11-07/HOOK_AUDIT.md`, verdict BORDERLINE). `gem5.opt` md5 `9ac3ac66…`. Flags `--stl-ann-file`, `--stl-store-stall-cycles N`, `--stl-alias-pred {no_alias,alias,off}`. Schemes as recon-modded: 0 Unsafe, 1 Delay/NDA-like, 2 STT, 3 DoM. Registry: `specs/gem5_builds.json` id `gem5-recon-stl`. |
| every other build (`/work/stt`, `gem5-recon-modded`, `gem5-spt`, the three amulet builds, amulet-STT) | no | port needed to run STL | Port = `gem5-hooks/stl/apply_stl_hooks.py <gem5_root>` (anchor-based, idempotent, refuses unless every anchor matches once) + rebuild. `stl_hooks_vs_gem5_v22.0.0.2.diff` is an older upstream reference, before the 2026-10-30 barrier/alias fixes. Rebuilds need Anna's OK (DECIDE). |

### Which defenses have STL in their threat model

| Unit (`specs/defense_units.json`) | STL in scope? | STL model | Runnable today? |
|---|---|---|---|
| 1 STT-Spectre, `/work/stt` | **no**: STT-Spectre casts no store shadow (`rob_impl.hh:444-495`); a bypass leak there is expected by design | (`STT_6_stl` only as a labelled control) | no hooks |
| 2 Recon-STT, recon scheme 2 | yes (`decode.cc:686-695` inserts stores into the shadow tracker) | `STT_6_stl` | **yes**, on `gem5-recon-stl` |
| 3 SPT-Fence (Spectre configs), `gem5-spt` | no (branch-only visibility point) | — | no hooks |
| 4 SpecLFB, amulet | yes (memory-order MUSLs, SpecLFB Sec. 5) | `STT_6_stl` as stimulus | no hooks |
| 5 ReCon, recon-modded | yes (same shadow tracker) | `Recon_6_stl` (draft) | partly: `gem5-recon-stl` has the hooks; ReCon mode there not verified |
| 6 InvisiSpec, amulet | Futuristic mode only (InvisiSpec Sec. IV Table I) | `STT_6_stl` as stimulus | no hooks |
| 7 CleanupSpec, amulet | yes (every transient instruction unsafe, Sec. 2.1) | `STT_6_stl` as stimulus | no hooks |
| 8 ReCon OTB | n/a (two-source merge shape) | — | — |
| 9 STT on SPT's sub-implementation | no | — | no hooks |
| 10 SPT variants, `FuturisticSafe*` configs | yes | `SPT_6_oneLP_stl` (draft, **generates nothing** yet) | no hooks |
| 11 Delay/NDA (recon scheme 1), 12 DoM (scheme 3) | probably (same shadow tracker; not verified in code) | `STT_6_stl` | on `gem5-recon-stl --scheme=1/3`, untested |
| STT-Futuristic (`/work/stt` + `configs/example/se_futuristic.py`) | yes | `STT_6_stl` | **PARKED** by Anna 2026-11-07 (`FUTURISTIC_MODEL.md`) |

### Models

| Model | Where | State | Generation result |
|---|---|---|---|
| `STT_6_stl` | `STAGE1_alloy/models/STT_6_stl.als` | **approved** 2026-10-28; `rf`-based alias fact | SAT; 60 in 5 s (500 earlier); 60/60 concretize |
| `Recon_6_stl` | `proposed/Recon_6_stl.als` | draft 2026-11-08, atom-based alias | 60 in 10 s; 60/60 concretize |
| `SPT_6_oneLP_stl` | `proposed/SPT_6_oneLP_stl.als` | draft 2026-11-08, atom-based alias | **0 in 900 s**: SPT's state-minimality (RS) vs the alias fact (section "STL for every main model"); a one-line RS exemption gives 60 in 10 s, 59/60 concretize (DECIDE) |
| `STT_6_shadows` | `proposed/STT_6_shadows.als` | draft 2026-11-07: Recon-STT's branch **or** store contract, no alias fact | minimal instances have one source, so its tests = `STT_6`'s + `STT_6_stl`'s (`STT_VS_RECON_STT.md`) |
| `STT_6_stl_core` (split, Stage 1) | `proposed_twophase/STT_6_stl_core.als` | draft, RI-only (RO+RI makes an STL core impossible) | **Stage-1 EXHAUSTED: 306 cores at ≤6 instructions** (Mac, 23 min) → `testsets/STT_6_stl__twophase_draft/stage1_xml`, log `~/Library/Logs/simspect/twophase_STT_6_stl.log` |
| `Recon_6_stl_core` (split) | `proposed_twophase/Recon_6_stl_core.als` | draft, RI-only | Stage-1 **running** since 13:58 (858 at 40 min; cap 20000, 4 h) → `testsets/Recon_6_stl__twophase_draft/stage1_xml`, log `twophase_Recon_6_stl.log` |
| `SPT_6_oneLP_stl_core_conservative` (split) | `proposed_twophase/` | draft, no RO/RI (SPT conservative convention) | UNSAT at ≤3 and ≤4 (same RS cause); not run |
| Stage 1.5 (pin + add) for any STL core | — | not built (the two-phase session owns Stage 1.5 for every family) | — |

Tools: `STAGE1_alloy/models/proposed/derive_stl.py` (main model → STL draft; reproduces `STT_6_stl` from `STT_6`), `STAGE1_alloy/model_source_matrix.py` (which speculation sources a model admits; `str_alias_atom` predicate), `proposed_twophase/derive_core.py` + `run_stage1.py` (split cores). Concretization: `parsexml.py` branch mode `stl_bypass` (`pass2_6_specify_stl`). Run config: `runconfigs/run_config_STT_6_stl.jsonc` (gem5-recon-stl, scheme 2, hold D = 5000, `no_alias`, fnc 150, `max_instances` 100000).

### Experiments

| Experiment | State | Result / where |
|---|---|---|
| Hook test: 60 `STT_6_stl` tests on `gem5-recon-stl`, configs A–F | **done** 2026-10-30 | valid bypass 58/60; STT 0/28 load transmitters sent in the window vs Unsafe 28/28; `alias` and D = 0 controls 0. cafe2 `results/STT_6_stl_hooktest/controls/` (section "Hook test") |
| Shadows store-only + alias: 60 tests, STT vs Unsafe vs `alias` | **done** 2026-11-07 | 59/60 valid; STT 0/32 sent vs Unsafe 32/32; `alias` 0. cafe2 `results/STT_6_shadows_draft/` (`stl_A_stt.json`, `stl_B_unsafe.json`, `stl_C_stt_alias.json`, `cfg_stl.jsonc`) |
| Full `STT_6_stl` testset + sweep (Recon-STT, unit 2) | **planned, blocked** | needs the STL window checker (not written; `check_ld`/`check_br` verdicts are not meaningful for STL tests: no `lc`, `fnc` = the store) and, ideally, a refreshed `gem5-recon-stl`. Until then score with `gem5-hooks/stl/stl_hooktest.py` |
| `Recon_6_stl` on `gem5-recon-stl` (unit 5) | planned | needs the draft approved; ReCon mode on that build unverified |
| `STT_6_stl` on schemes 1 and 3 (units 11, 12) | planned | untested; shadow-tracker sharing across schemes not verified |
| STL on amulet ×3 and `gem5-spt` (units 4, 6, 7, 10) | not started | needs the hook port + rebuilds (DECIDE) |
| SPT STL generation | blocked | RS DECIDE |
| Stage-1 STL cores | 1 done (STT, 306), 1 running (Recon), 1 blocked (SPT) | see Models |

### Open decisions (all in `URGENT_TODO.md`)

- Approve `Recon_6_stl` (recommended) and, after the RS call, `SPT_6_oneLP_stl`.
- SPT STL: (a) exempt the alias location from RS (recommended), (b) drop RS, or (c) skip SPT STL for now.
- Alias fact: `rf` (approved `STT_6_stl`) vs atom-based (the new drafts; superset, works without `rf_from_most_recent_writer`). Re-deriving `STT_6_stl` with `--alias atom` gives 60 in 7 s, 60/60.
- Approve `STT_6_shadows`, and whether it needs a true-alias fact.
- STL hooks: (i) rebuild `gem5-recon-stl` from today's recon-modded (recommended first), (ii) port to amulet ×3 + `gem5-spt`.
- `stl_bypass` annotates every aliasing load, not only the first: OK as the semantics?
- Window checker design (below), including accepting a squash caused by S of any load at or before L (gem5 checks violations at 16-byte granularity).
- Contract granularity: every instruction after an unresolved store (encoded), or only loads that may alias it?
- Whether the forced memory-dependence prediction counts as "the predictor" under the hook rule (HOOK_AUDIT borderline).

### Lessons (things that produced wrong answers or failures)

- **Shared `Mem_s` atom ≠ `rf` edge.** The model lets a store and a load name the same location with no `rf` edge; they still alias in the concrete program. An `rf`-based alias filter misses them (37/60 of atom-alias instances had no `rf` edge).
- **A store-source instance without a true alias doesn't concretize**: its store usually has no location (`outmem` is `set`, can be empty), so `stl_bypass` fails with "no specified outmem". Under Recon-STT such a load is still "speculative", but nothing transient happens.
- **Minimality keeps one source per instance**: branch + store together found nothing in 25 min, because the older source's shadow covers the younger one.
- **RO+RI minimality makes an STL core impossible**; RI-only is required (306 cores at ≤6).
- **SPT protects a load's output regardless of the location read**, which is why its RS-minimality kills every aliasing instance.
- **gem5 detects memory-order violations at 16-byte granularity**: the squash can name an older load 8 bytes from S.
- **Hook bugs fixed 2026-10-30**: the litmus setup `mfence` sends dispatch down the barrier path (override applied there too); priming the store set fails for `alias` (the load now depends on the store's seqNum directly).
- **Harness gotchas**: `stl_hooktest.py` needs an absolute testdir (fixed in the repo copy 2026-11-07); ship tarballs to cafe2 with `COPYFILE_DISABLE=1` (macOS `._*` files break asm); cafe2 has no `a6CountModels.class`, so generate XML on the Mac.
- **Signal on recon builds**: the real cache send is `Memory request (pkt: …) from inst [sn:N] was sent` (`lsq_unit.cc:1546`), not `Doing memory access`; `check_ld`'s gate keys on a line that doesn't exist there (`wiki/findings/bug/recon_cache_reach_gate/`).

## Status

| Piece | State |
|---|---|
| Model `STAGE1_alloy/models/STT_6_stl.als` | written (Anna approved new `.als` files), SAT, 500 instances enumerated locally in a few seconds |
| Concretization, branch mode `stl_bypass` | written + tested: 500/500 instances concretize and compile to x86; the existing modes are byte-identical before/after (120/120 STT_6 `.ll` + `.ann.json`). 2026-10-30: every true-alias load is annotated, not only the first (2/60 tests gain a second one) |
| Harness flags (`gem5.stl_*` → `SIMSPECT_STL_*` → `--stl-*`) | written; off unless a config sets `gem5.stl_ann_enable` |
| gem5 hooks `gem5-hooks/stl/` | **built** into `/work/gem5-recon-stl` (copy of gem5-recon-modded, 2026-10-30); two hook bugs found and fixed by the controls; all controls pass on 60 tests (see Hook test) |
| Window checker | proposed below, **still not written** (2026-11-08) |
| STL models for the other main models (2026-11-08) | drafts `proposed/Recon_6_stl.als`, `proposed/SPT_6_oneLP_stl.als` via `proposed/derive_stl.py`; split cores in `proposed_twophase/`. Recon works; SPT generates nothing yet (see "STL for every main model") |

## The primitive: a false-negative alias prediction

The store's address is unresolved when a younger load to the same address issues. The memory-dependence predictor says "no alias", so the load does not wait. It reads the stale value (the store's queue entry has no address yet, so the forwarding scan skips it), and its dependents, the transmitter among them, run on that value. When the store's address resolves, the LSQ sees that a younger load to the same address already executed (a memory-order violation) and squashes from that load. The window is load issue → that squash. This is Spectre v4 (speculative store bypass), and the analog of an unresolved, mispredicted branch: the bypass path only ever runs speculatively.

The false-positive direction (predict alias, addresses differ) opens no window in gem5: O3's store sets only make the load wait; there is no predictive forwarding. It is kept as a negative control (`--stl-alias-pred=alias`).

STT's paper covers this only in its Futuristic threat model, **but the Recon builds' STT does cover it** (see Threat model below). STT p5: "In the Spectre model, an instruction has reached the visibility point if all older control-flow instructions have resolved. In the Futuristic model, an instruction has only reached this point if it cannot be squashed." STT §6.4.2 frames memory-dependence speculation as "simply a prediction of the store-to-load forwarding implicit branch". Source: `~/Documents/quail/sources/papers/yu-2019-stt.pdf`.

## Generation: `STT_6_stl.als`

A copy of `STT_6.als`, with changes only in the STL block and the defense block. `STT_6.als` is untouched. Every instance has an unresolved store S, a load L after it that reads S's `Mem_s`, and L's value flowing to the transmitter. In the 500 enumerated instances, 500/500 have the transmitter fed by a load of S's location, which the state-minimality clause (`all s: State | secure[RS->s]`) forces. 39/40 of a first sample have no committed instructions (S is the first non-committed).

```diff
+fun has_unresolved_strs_p[p: PTag->univ] : Instruction {
+	((unresolved_p[p] & Stores).(^(spo_p[p]))) // all the instructions that come after a store with an unresolved address
+}
+fun no_unresolved_strs_p[p: PTag->univ] : Instruction {
+	i_p[p] - has_unresolved_strs_p[p]
+}
+
+// control-flow speculation is off in this model
+fact stl_no_unresolved_branches {no (unresolved & (Branchxs+Branchns))}
+
+// true alias (the false-negative prediction): some load at or before the xmit
+// reads the memory state an older unresolved store writes (rf = most recent
+// writer, so no intervening store to that state)
+fact stl_alias_pair {
+	some s: unresolved & Stores, l: uncommitted & Loads |
+		some (s.outmem.rf & l.inmem) and l in xm + xm.^(~spo)
+}
 ...
-fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}
+fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_strs_p[p]}
 ...
-	s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate
+	s - (Loads & no_unresolved_strs_p[p] & i).inmem.opstate // loads with no unresolved-address store before them remove their inmem state from the protset
```

- **Speculation source.** `has_unresolved_strs_p` mirrors `has_unresolved_brs_p`: everything after a store whose address is unresolved (`isresolved` on a store = its address is known).
- **Contract.** Uncommitted and after an unresolved store, in place of after an unresolved branch.
- **Protset propagation.** A load with no unresolved store before it declassifies its location, mirroring the branch rule.
- **No control-flow speculation.** All branches are resolved, as asked. The transmitter branch keeps the existing xmit override in concretization: it is the observable, not the speculation source.
- **True alias.** The fact is the generation half of "false negative": without it, a load past an unresolved store is speculative under the contract but never squashed in gem5, and the value it reads is the architectural one.
- **Minimality.** The existing `all i: (unresolved - first_uncommitted) | secure[RR->i]` already ranges over stores, so every unresolved store must matter. Unresolved loads or ALU ops can't appear except as the boundary instruction.

To check against the papers (Anna, 2026-10-28: "we will have to read the papers again"): whether STT's Futuristic contract marks every instruction after an unresolved store as unsafe (what this encodes), or only loads that may alias it.

## Concretization: branch mode `stl_bypass`

Turned on only by putting `"stl_bypass"` in `speculation.branch_modes` (or `batch_generate.py --mode stl_bypass`). The other modes never call the new code. Output goes to its own per-mode tree, `testsets/<model>/stl_bypass/`, so it is a parallel pipeline.

- `pass2_5_specify_branches` accepts the mode and refuses an instance with an unresolved non-xmit branch (STT_6 XMLs are rejected, 3/3 tried). Resolved branches become `correctly_not_taken` exactly as before.
- New `pass2_6_specify_stl` pairs each unresolved store S with its bypass load L: the first uncommitted load after S that reads S's `Mem_s` before another store writes it (the model's most-recent-writer rule). Pairs are tags on the instruction records, because `pass_interleave` renumbers PCs. A missing pair raises, so the test is skipped and logged.
- **Making the alias real at runtime.** A load or store with a specified `inaddr` is emitted as `probe_mem + reg` and ignores its `Mem_s` slot, so model-level aliasing isn't guaranteed. When neither S nor L has `inaddr`, they share the `mem_base` slot and nothing changes (487/500). Otherwise (13/500) S is re-emitted at L's runtime address, relative to L's base and keeping S's own index register: `movq src, D(base, r_S, 1)` or `movq src, D(base)`. D comes from a small architectural evaluator over the straight-line program (`_stl_arch_values`). It mirrors the emitted asm, evaluates twice to check L's address doesn't depend on the re-targeted store, and raises on anything it can't evaluate exactly. Loads and stores are already inline asm, so LLVM cannot fold the store→load.
- `.ann.json` gains `"stl_annotations": [{store_pc, load_pc, mem_atom, mode}]`, and `compile_annotate.py` adds absolute `store_addr` / `load_addr` (the pc marker sits on the `movq` itself).

## gem5 hooks (`gem5-hooks/stl/`)

`apply_stl_hooks.py <gem5_root> [--dry-run]` inserts both hooks by anchor string, not line number (Recon's o3 files are heavily modified). It is idempotent (marker `SimSpect-STL`), writes nothing unless every anchor matches exactly once, and saves originals as `<file>.pre-stl`. `stl_hooks_vs_gem5_v22.0.0.2.diff` is the reference diff from applying it to upstream gem5 v22.0.0.2, which is the version whose `iew.cc` line numbers match Recon's (`recon-modded_src.diff` hunks at `iew.cc:1247`).

| Flag | Hook | Where |
|---|---|---|
| `--stl-ann-file <ann.json>` | supplies the (store_addr, load_addr) pairs | `configs/example/se.py` → CPU params |
| `--stl-store-stall-cycles N` | **store address-generation hold.** An annotated store is sent back to the mem-dep replay list (`IEW::rescheduleMemInst`, the LSQ's own path for a load it can't execute yet) instead of computing its address, and an event replays it N cycles after it first issued. An early replay re-defers it. | `cpu/o3/iew.{hh,cc}` |
| `--stl-alias-pred {no_alias,alias,off}` | **prediction override** for the annotated loads: `no_alias` ignores the store-set answer (false negative, the primitive); `alias` makes the load depend directly on the paired store's in-flight seqNum, so it waits (false-positive control). Both modes also apply when a load barrier is in flight (`via=barrier`); `off` = unmodified | `cpu/o3/mem_dep_unit.{hh,cc}` |

Why the existing pieces weren't reused: the recon-modded store "resolve stall" placeholder (`iew.cc` ~1247) fires *after* `executeStore`, so the address is already known. The unwired `AnnotatedStoreSet` (`store_set_annot.cc`) primes the store set in the load's `checkInst`, after the store has already been inserted into the LFST without a set ID, so the forced dependence would miss the first dynamic instance.

Print-only trace lines, under the existing `O3PipeView` flag in the [`SIMSPECT_HOOKS.md`](SIMSPECT_HOOKS.md) format:

```
O3PipeView:simspect:<tick>:STL:stl_hold:line=-:seq=<S sn>:pc=<S pc>:victim=-:cause=-:sq=-:id=-
O3PipeView:simspect:<tick>:STL:stl_release:line=-:seq=<S sn>:pc=<S pc>:...        # hold over; S computes its address now
O3PipeView:simspect:<tick>:STL:pred_no_alias:line=-:seq=<L sn>:pc=<L pc>:...:cause=<dep sn>
O3PipeView:simspect:<tick>:STL:mem_order_squash:line=-:seq=<L sn>:pc=<L pc>:...:cause=<S sn>   # every violation, annotated or not
```

Harness: run config `gem5.stl_ann_enable`, `gem5.stl_store_addr_stall_cycles`, `gem5.stl_alias_pred` → `pipeline._build_gem5_env` → `SIMSPECT_STL_*` → `gem5_common.run_gem5` appends `--stl-ann-file=<test>.ann.json --stl-store-stall-cycles=N --stl-alias-pred=X`. Example config: `runconfigs/run_config_STT_6_stl.jsonc`. Its D = 5000 mirrors `sweep.unresolved_stall_cycles` in `run_config_STT_6.jsonc`.

## Threat model of the build (answered 2026-10-30)

`gem5-recon` / `gem5-recon-modded` / `gem5-recon-stl` STT (scheme 2) is **not** STT's Spectre model: a load is unsafe while any older conditional branch is unresolved **or any older store has no address yet**. So the STL primitive is in scope there.

- Recon paper Sec. 3: "For evaluation, we use only speculation cast by control flow and store instructions"; Sec. 6: "Speculation state is tracked through shadows [...] triggered by control and store instructions", "closer to the Spectre threat model [...] rather than the Futuristic threat model" (`~/Documents/quail/sources/papers/aimoniotis-2023-recon.pdf`).
- Code: `src/cpu/o3/decode.cc:686-695` inserts every conditional branch and every store into the shadow tracker and marks a load speculative if any shadow exists; `secure_scheme/shadow_tracker.cc` frees a store shadow when `effAddrValid()` and a branch shadow when `branchResolved()`; `taint_tracker.cc:138` untaints when the load is no longer speculative. Exceptions are tracked but never inserted ("Currently unused").
- `/work/stt` is different: `--threatModel` Spectre (branches only) or Futuristic (all older instructions completed, `rob_impl.hh:493-512`); the SimSpect harness pins it to Spectre (`gem5-hooks/stt/se_exp.py:332`), where STL is out of scope. See [`FUTURISTIC_MODEL.md`](FUTURISTIC_MODEL.md).

## Hook test (2026-10-30)

Build: `/work/gem5-recon-stl/build/X86/gem5.opt` (md5 `9ac3ac66…`), built with `/usr/bin/scons` (SCons 3.1.2; `/usr/local/bin/scons` 2.5.1 doesn't run on Python 3.8). Applied diff: `gem5-hooks/stl/stl_hooks_vs_gem5-recon-modded.diff`. Testset: 60 `STT_6_stl` instances (XML from the Mac, cafe2 has no `a6CountModels.class`), `testsets/STT_6_stl/stl_bypass/` on cafe2. Driver: `gem5-hooks/stl/stl_hooktest.py <testdir> <scheme> <out.json>` (env `SIMSPECT_GEM5_BIN`, `SIMSPECT_SE_CONFIG`, `SIMSPECT_STL_*`, `LC_ALL=C.UTF-8`); per-config JSONs in cafe2 `results/STT_6_stl_hooktest/controls/`.

| config | valid bypass (hold + no-alias + L before release + squash caused by S) | ld transmitter (28) sent to memory inside [hold, release) |
|---|---|---|
| A: STT (scheme 2), no_alias, D=5000 | 58/60 | **0/28**: STT's delay unit holds every one |
| B: Unsafe (0), no_alias, D=5000 | 58/60 | **28/28**: the primitive opens a real window |
| C: STT, alias | 0/60 (no load bypasses) | 0 |
| E: Unsafe, alias | 0/60 | 0 |
| F: Unsafe, no_alias, D=0 | 0 (no hold) | 0 |

The 2 non-valid tests in A/B (`inst-000020`, `-023`) did bypass: gem5 checks memory-order violations at 16-byte granularity, so the squash names an older load 8 bytes from S, and L is squashed with it. The gate should accept a squash caused by S of any load at or before L.

Bugs the controls found, both fixed:
1. **Hook:** the litmus setup `mfence` (`parsexml.py:2058`) is still in flight when S and L dispatch, so `MemDepUnit::insert` takes the barrier path and never asks the predictor. The override now also applies there (`via=barrier`).
2. **Hook:** priming the store set does not work for `alias`. `StoreSet::issued()` drops the held store from the LFST as soon as it issues, so a load dispatched after that got no dependence (9/60 still bypassed). Now the load depends directly on the paired store's seqNum (`MemDepUnit::stlAliasDep`).
3. **Concretization:** only the first aliasing load was annotated; in `inst-000006` a second load of the same slot feeds the transmitter and bypassed through the cold predictor even under `alias`. `pass2_6_specify_stl` now tags every load of S's location before the next writer; `.ann.json` gets one entry per load (`role` bypass/alias), keeping only loads whose runtime address equals S's.

**Signal on recon builds.** The real cache send is `Memory request (pkt: …) from inst [sn:N] was sent` (`lsq_unit.cc:1546`). `Doing memory access` is not a send: STT's delay unit bounces a tainted load after it (`lsq_unit.cc:2104`). See the gate finding in `wiki/findings/bug/recon_cache_reach_gate/`.

## Proposed window check (not built)

Per test: S, L and the xmit X are known by address from the ann. All times come from one pipeview trace (`O3PipeView` + `LSQUnit`).

1. **The primitive fired: validity gates.** If any gate fails, the test is `stl_invalid` with the reason, counted neither as leak nor as no-leak.
   - `stl_hold` for S's first dynamic instance (else the hooks aren't in this binary).
   - With `no_alias`, a `pred_no_alias` line for L.
   - L's first dynamic instance executes (LSQUnit "Executing load") before `stl_release`: the bypass happened.
   - Its fate isn't `store_forward`.
   - A `mem_order_squash` with `cause` = S and `seq` = an instance at or before L's first instance (16-byte violation granularity can name an older neighbour): the alias was real. No squash means a concretization bug.
2. **Which X counts.** Only X's *first* dynamic instance: younger than S, at or after L's first instance, and squashed by that `mem_order_squash`. After the squash, L and X re-execute with the right value, and that replay is architectural. That differs from the branch checkers, which match the xmit by PC.
3. **Window.** `t(stl_hold) ≤ signal < t(stl_release)` is the strict contract bound: X transmits while S's address is unresolved. Also record `signal < t(mem_order_squash)`, the transient bound; the two differ by a cycle or two. Don't reuse the branch window `lc_retire < signal < fnc_retire`. There is usually no committed instruction (no `lc`). `fnc` = S retires after the squash and the commit stall, so the replayed X would land in-window: a false positive.
4. **Signal and gate per transmitter kind.**
   - For `ld`: the real-send tick (`Memory request … was sent` on recon builds; `successfully sent out packet(s)` on /work/stt and gem5-spt) or store-forward completion, keyed by X's instance seq, not by PC. The shared `check_ld._xmit_cache_fate` cannot be reused as-is on recon builds (see the gate finding).
   - For `br_x`, the redirect tick check_br already uses, now with the window enforced (closing check_br's known gap for these tests).
   - Implement this as one shared `stl_window(trace, ann)` in `gem5_common.py` that `check_ld` / `check_br` call when `ann` has `stl_annotations`, not as a new checker family.
5. **Controls, run before reading any STT hit.**
   - Unsafe baseline (scheme 0) + `no_alias`: nearly every valid test should leak, which shows the primitive works.
   - Any scheme + `alias`: L waits for S, no squash, so 0 leaks. A hit here is a checker bug.
   - Hold sweep, e.g. D ∈ {0, 50, 500, 5000}: at D = 0 the bypass should mostly vanish.
6. **Bucketing.** `stl_invalid` reasons become an error-bucketing diagnostic in the run's `diagnostics/`, per the diagnostics rules.

## Open

- **Answered:** build = copy `/work/gem5-recon-stl` (Anna, 2026-10-30); threat model = control + store shadows (above).
- **Window checker** still to write (above), then a full STT_6_stl testset + sweep. The 60-test result already says STT holds on these shapes.
- **Contract granularity.** Is "everything after an unresolved store" right for STT Futuristic, or only loads that may alias it? See Generation.
- **Other defenses.** Drafted 2026-11-08 (next section). The hooks still port by re-running `apply_stl_hooks.py` on each tree; only `/work/gem5-recon-stl` has them today.

## STL for every main model (2026-11-08)

`STAGE1_alloy/models/proposed/derive_stl.py <main>.als <out>.als [--alias atom|rf]` applies exactly the edits that turned `STT_6.als` into `STT_6_stl.als`: the STL source block (`has_unresolved_strs_p`, `no_unresolved_strs_p`, all branches resolved), the alias fact, the contract switched to stores, and the branch-keyed protection-set line switched to stores where the model has one. Every anchor must match once or it refuses. Self-check: `--alias rf` on `STT_6.als` gives code identical to `STT_6_stl.als` (ignoring comments and whitespace).

The drafts use the atom-based alias (`--alias atom`, default): every unresolved store has a younger uncommitted load at or before the transmitter naming the same `Mem_s`, with no other store to it in between. Reasons: it is a superset of the `rf` version (more tests); Recon_6 and SPT_6_oneLP lack `rf_from_most_recent_writer`, which the `rf` version relies on for "no store in between"; and in SPT an `rf` edge from the store would let its forwarding rule treat the bypassing load as getting the store's value, which is the opposite of a bypass.

| Model | Alloy, exactly 6 | `stl_bypass` concretization | Split core (Stage 1) |
|---|---|---|---|
| `STT_6_stl` (approved, `rf` alias) | 60 in 5 s | 60/60 | `STT_6_stl_core.als`, RI-only: 200 (capped) at ≤3 in 12 s and at ≤4 in 67 s |
| `STT_6` + atom alias (scratch, for comparison) | 60 in 7 s | 60/60 | — |
| `Recon_6_stl` (draft) | 60 in 10 s | 60/60 | `Recon_6_stl_core.als`, RI-only: 200 at ≤3 in 31 s, at ≤4 in 165 s |
| `SPT_6_oneLP_stl` (draft) | **0 in 900 s** | — | `SPT_6_oneLP_stl_core_conservative.als` (no RO/RI): **UNSAT** at ≤3 (34 s) and ≤4 (326 s) |

**Why SPT generates nothing.** SPT's protection seed protects every operand except unfed register/address inputs (`SPT_6_oneLP.als:341`), so a speculative load's output is protected whatever location it reads. The aliased `Mem_s` is then never necessary for the leak, and state-minimality (`all s: State | secure[RS->s]`) rejects every instance in which the store and the load share it, which the alias fact requires. Probes on the ≤3 core: RS off gives 50 instances in 5 s; the alias fact off gives 50 in 16 s; the perturbation-aware seed from the 2026-11-07 SPT probe still gives 0; RS with the alias location exempt (`all s: State - (unresolved & Stores).outmem.opstate | ...`) gives 50 in 8 s, and on the full model 60 in 10 s at exactly 6, of which 59/60 concretize. The one failure is a `parsexml` edge case: `stl_bypass: bypass load address probe+-1 out of bounds` in `_stl_store_retargets` (`parsexml.py:1208`), not investigated. The fix is a generation-predicate choice, so it is a DECIDE in `URGENT_TODO.md`; the draft stays as derived.

**Running STL tests needs the STL hooks** (store-address hold and the forced no-alias prediction), and only `/work/gem5-recon-stl` has them. That build is stale: it predates the 2026-10-30 resolve hooks (`wiki/findings/audits/2026-11-07/HOOK_AUDIT.md`). Which defenses have STL in their threat model, per build: `STAGE1_alloy/models/MANIFEST.md` ("Defenses we test").
