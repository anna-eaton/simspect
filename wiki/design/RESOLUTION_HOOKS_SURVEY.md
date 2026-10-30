# Branch-resolution hooks: survey of instrumented gem5 builds (2026-10-29)

Read-only survey. Nothing on cafe2 was changed and no gem5 was run. Every claim cites a file:line in the live trees under `/work` in the `gem5_dev` container on cafe2 (read 2026-10-29), or a repo file. Line numbers are for the live trees, not the `gem5-hooks/` snapshots.

## TL;DR

1. **Eight builds carry the branch-force + resolve-stall + fnc-commit-stall hooks:** gem5-recon-modded, stt, stt-dbg, gem5-spt, and all four amulet AE trees (InvisiSpec, CleanupSpec, SpecLFB, **and amulet-STT**). gem5-recon (control) and sdo have none. No build has the STL hooks.
2. **`specs/gem5_builds.json` is stale for amulet-STT.** It says fnc-stall is "not confirmed". The live tree has it in commit, cpu and O3CPU.py, se.py wires it at lines 351-352, and the binary (2026-05-27) is newer than the source edit (2026-05-21).
3. **Accepted annotation keys:** stt, stt-dbg and all four amulet builds accept `branch_addr[_hex]` first, then `branch_pc_addr[_hex]`, then x86 offsets. **gem5-spt and gem5-recon-modded accept only `branch_pc_addr[_hex]` plus x86 offsets** (the 2026-10-29 finding is confirmed). `gem5_common._branch_ann_for_se` (uncommitted, `STAGE3_gem5/gem5_common.py:156-174`) now adds the alias.
4. **Today's resolution estimate is the IEW release tick, not the moment the defense sees the branch resolve.** On every build, the hook calls `updateExeInstStats` when it *schedules* the release, and `updateExeInstStats` is what sets the O3PipeView `complete` tick. So `complete` is the pre-stall execute tick, and `complete + stall*tpc` is exactly the tick the `stallBcast` event fires. It is right only if the stall was actually registered, which was false on spt/recon-modded before the alias fix. It also leaves out two later steps on every build. First, commit marks the branch `canCommit` one cycle later (`iewToCommitDelay=1`), and that is what every defense's notion of "resolved" keys on. Second, under STT's implicit channel, a tainted branch's squash can be held "pending" until untaint.
5. **Proposal:** add print-only `O3PipeView:simspect:<tick>:BR:<kind>` lines. Use `resolve_hold` / `resolve_release` / `resolve_drop` in the IEW hook lambda, and `resolve_visible` in `markCompletedInsts` after `setCanCommit()`. Parse them with the existing `parse_simspect_line`. Each build needs about 15 lines in two files that already include `debug/O3PipeView.hh`. All 8 hooked builds can take it at low effort. sdo would need the full port first.
6. **Zero-rebuild stopgap:** the Commit flag is already always on (`gem5_common.py:187-188`). Commit already prints `Marking PC <pc>, [sn:N] ready within ROB.` at the defense-visible resolution point on every build. Parsing that line gives `visible_tick` today.

## A. Builds and their hooks

Columns: **BTB** = `btbForcedTargets` override in `bpred_unit.{cc,hh}`. **RS** = per-branch resolve stall (`annotationResolveStallCycles` → `getResolveStallCyclesFor` → deferred `stallBcast` event in IEW). **FNC** = `fncCommitStallPC/Cycles` in commit. **STL** = `stlStallStorePCs` / `stlAliasPred` (`gem5-hooks/stl/`). **SimSpect ev** = print-only `O3PipeView:simspect` cache/defense events (`wiki/design/SIMSPECT_HOOKS.md`).

| build | path | gem5 base / scons | BTB | RS | FNC | STL | SimSpect ev | other |
|---|---|---|---|---|---|---|---|---|
| gem5-recon | /work/gem5-recon | 22.0.0.2 (`src/base/version.cc`), py3 | no | no | no | no | no | control by design |
| gem5-recon-modded | /work/gem5-recon-modded | 22.0.0.2, py3 | yes | yes (`iew.cc:1313`; prints `[ResolveStall]` under the **IEW** flag, which is off by default) | yes (`commit.cc:1005-1016`) | no (only the unwired `store_set_annot`, an `lsq_unit` `STL_CHECK` DPRINTF, and dead store- and commit-stall placeholders in `iew.cc`) | no | pcstate hooks |
| stt | /work/stt | cwfletcher/stt (old, template `DefaultIEW<Impl>`), py2 scons 2.5.1 | yes | yes (`iew_impl.hh:1337-1358`) | yes (`commit_impl.hh:1209-1222`) | no | no | `se_exp.py`, `se_slowcomm.py` |
| stt-dbg | /work/stt-dbg | same as stt | yes | yes (`iew_impl.hh:1337`) | yes | no | no | `POCVAL` DPRINTF in `lsq_unit_impl.hh` (`gem5-hooks/stt-dbg/stt-dbg.patch:318-333`) |
| gem5-spt | /work/gem5-spt | FPSG-UIUC/SPT (old), py2 | yes | yes (`iew_impl.hh:1379-1400`) | yes (`commit_impl.hh:1219-1232`) | no | no | se.py `--scheme=2`→SpectreSafeFence |
| amulet-InvisiSpec | /work/amulet/amulet-gem5-InvisiSpec_AE-v1.1 | old (template), py2, Ruby | yes | yes (`iew_impl.hh:1331-1352`) | yes (`commit_impl.hh:1039-1052`) | no | yes | |
| amulet-CleanupSpec | /work/amulet/amulet-gem5-CleanupSpec_AE-v1.1 | old, py2, Ruby | yes | yes (`iew_impl.hh:1430-1451`) | yes (`commit_impl.hh:1044-1053`) | no | yes | |
| amulet-SpecLFB | /work/amulet/amulet-gem5-SpecLFB_AE-v1.1 | 22.1.0.0, py3, classic | yes | yes (`iew.cc:1302-1323`) | yes (`commit.cc:1005-1016`) | no | yes | `--branch-ann-base` hex-parse fix (`configs/common/Options.py:543-546`) |
| amulet-STT | /work/amulet/amulet-gem5-STT_AE-v1.1 | old, py2; binary is `build/X86/gem5.opt` (not MESI) | yes | yes (`iew_impl.hh:1336-1357`) | **yes** (`commit_impl.hh:1209-1222`; se.py:351-352) | no | no | registry says fnc "partial", which is stale |
| sdo | /work/sdo | cwfletcher/sdo @ 5d058fd, no `build/` dir | no | no | no | no | no | never built |

Build-vs-source timestamps (binary / newest hook source): recon-modded 05-21 05:19 / 05-21 05:01. stt 05-21 05:41 / 05-21 05:28. stt-dbg 06-03 / 05-21. spt 05-28 09:29 / 05-28 09:10. InvisiSpec 10-28 / 06-08. CleanupSpec 10-28 / 06-08. SpecLFB 10-28 / 06-08. amulet-STT 05-27 / 05-21. Every binary is newer than its hook source.

The resolve-stall lambda is the same in all 7 old-style and SpecLFB builds. On `isSquashed()` it returns. Otherwise it runs `setExecuted(); instToCommit(); if (mispredicted()) squashDueToBranch(...)`, and it is scheduled at `cpu->clockEdge(stall)`. recon-modded has the same logic with IEW DPRINTFs (`gem5-hooks/gem5-recon-modded/recon-modded_src.diff`, iew.cc hunk at 1299).

## A2. Annotation keys each se.py loader accepts

| build | branch PC keys, in priority order | relative needs `--branch-ann-base` | stall key | target keys |
|---|---|---|---|---|
| stt, stt-dbg (`se.py:74-83`) | `branch_addr_hex`, `branch_addr`, `branch_pc_addr_hex`, `branch_pc_addr`, then rel `x86_branch_offset[_hex]`, `x86_pc_offset[_hex]` | yes (`Options.py:306`, optparse `long`) | `resolve_stall_cycles` | `btb_forced_target_addr[_hex]` / `btb_forced_target_x86_offset[_hex]` (only for non-not-taken modes) |
| amulet InvisiSpec (`se.py:75-81`), CleanupSpec (`:76-82`), STT (`:75-81`), SpecLFB (`:78-84`) | same as stt | yes (SpecLFB argparse with hex fix) | same | same |
| **gem5-spt** (`se.py:63-66`) | `branch_pc_addr_hex`, `branch_pc_addr`, then rel `x86_pc_offset[_hex]`, `x86_branch_offset[_hex]`. **No `branch_addr`.** | yes (`Options.py:304`) | same | same |
| **gem5-recon-modded** (`se.py:110-115`) | `branch_pc_addr_hex`, `branch_pc_addr`, then rel `x86_branch_offset[_hex]`, `x86_pc_offset[_hex]`. **No `branch_addr`.** An entry with no match is skipped with a `warn` (se.py loop). A non-stall mode with no target is also skipped. | yes (`Options.py:529`, `int(x,0)`) | same | same |

Consequence: before the `_branch_ann_for_se` alias, campaigns on spt and recon-modded ran with **no BTB force and no resolve stall**. The checker still computed `prop_tick = complete + stall*tpc` from `branch_addr` (`gem5_common.py:693`), so on those builds the "branches still unresolved" gate was evaluated against a stall gem5 never applied. The same mismatch was found and fixed for bugsynth only on 2026-06-08 (`claudelog.md:957`).

## B. How resolution is measured today and where the hook really releases

### Today

`collect_unresolved_branches` (`STAGE3_gem5/gem5_common.py:679-705`) takes each annotation with `resolve_stall_cycles>0` and resolves its PC from `branch_addr`, or legacy `x86_branch_offset`+base. `check_branch_resolutions` (`:708-736`) takes `best_record(by_pc[pc]).complete`, sets `prop_tick = complete + stall*ticks_per_cycle`, and returns ok iff `xmit_complete < prop_tick`. A branch with no complete record counts as ok ("not completed").

### What `complete` actually is

On every build, O3PipeView `complete` is set in `updateExeInstStats` (stt `iew_impl.hh:1656/1664`, spt `:1693/1701`, InvisiSpec `:1640/1648`, CleanupSpec `:1743/1751`, amulet-STT `:1655/1663`, SpecLFB `iew.cc:1620/1628`, recon-modded `iew.cc:1692/1706`). The hook calls `updateExeInstStats(inst)` right after `cpu->schedule(...)` and before the stall (stt `iew_impl.hh:1356-1357`, and likewise in every build). So `complete` is the execute tick. `executeInsts` runs on a clock edge, and `clockEdge(n)` is the current edge plus n periods, so `complete + stall*tpc` equals the event's fire tick. **The estimate is exact for the IEW release, as long as gem5 registered the stall.**

### The chain of events after release (all builds, O3 core)

1. **IEW release** (`stallBcast` fires, at `Default_Pri`=0, before the `CPU_Tick_Pri`=50 tick at the same tick; `src/sim/eventq.hh:149,162`): `setExecuted`, `instToCommit` (into `iewQueue`), and for a mispredict `squashDueToBranch`, which writes `toCommit->squash/squashedSeqNum/mispredictInst` (stt `iew_impl.hh:482-505`).
2. **Commit marks it resolved** one cycle later (`iewToCommitDelay=1`, stt `O3CPU.py:108`, recon `BaseO3CPU.py:117`). `markCompletedInsts` calls `setCanCommit()`, so `readyToCommit()` becomes true: stt `commit_impl.hh:1585/1600`, spt `:1694/1709`, InvisiSpec `:1403/1418`, CleanupSpec `:1419/1434`, amulet-STT `:1585/1600`, SpecLFB `commit.cc:1383/1397`, recon-modded `commit.cc:1463/1477`. **This is the defense-visible resolution on every build** (see the table below).
3. **Squash broadcast**: commit logs `Squashing due to branch mispred PC:` (stt `commit_impl.hh:1041`, spt `:1051`, InvisiSpec `:887`, CleanupSpec `:891`, SpecLFB/recon `commit.cc:838`). This is already parsed by `parse_commit_squashes` (`gem5_common.py:528-548`). Fetch then redirects after `commitToFetchDelay=1`.
4. **STT/SPT-family implicit channel only:** if the branch `isArgsTainted()`, commit marks it pending instead (`(Lazy) A branch mispredicInst ... is made pending`, stt `commit_impl.hh:934-953`). It is released later by `getResolvedPendingSquashInst` once untainted (`rob_impl.hh:889-900`, `commit_impl.hh:964-970`, printing `(Lazy) Squashing due to branch mispred` at `:1113`). Fetch also defers tainted redirects (`fetch_impl.hh:1021-1070`).
5. **If the branch is squashed by an older event before the release**, the lambda returns early and nothing is printed. The estimate still reports a `prop_tick` as if the branch had resolved.

### Each defense's own "branch resolved" notion

| build | what counts as resolved | where the defense consumes it |
|---|---|---|
| stt / stt-dbg / amulet-STT | `ROB::updateVisibleState`: a control inst blocks `prevBrsResolved` while `!readyToCommit()` / fault / squashed (stt `rob_impl.hh:444-495`, amulet-STT `:452`), called from `markCompletedInsts` (`commit_impl.hh:1607`) | VP = `isUnsquashable(true)` when `isPrevBrsResolved()` (Spectre) in `lsq_unit_impl.hh:1018,1051,1075` (amulet-STT `:1022,1055,1079`); taint recomputed in `rob->compute_taint()` (`commit_impl.hh:1611`) the same cycle; branch squash may be made pending (step 4) |
| gem5-spt | same, but skips squashed insts (`rob_impl.hh:498-545`); `applyDDIFT` VP check in the same loop | `lsq_unit_impl.hh:1217,1237`; `inst_queue_impl.hh:1143` `updateVisibleState`; untaint fwd/bwd (`cpu.cc:646-651` stats); commit `:1716` |
| gem5-recon-modded | `branchResolved(true)` for `isCondCtrl` in `markCompletedInsts` (`commit.cc:1480`); branch inserted unresolved at decode (`decode.cc:686-688`) | `ShadowTracker::freeBranches` frees the shadow (`secure_scheme/shadow_tracker.cc:218-226`), then `freeSpecInsts` clears `setSpeculative(false)` (`:279-293`), both on `cpu.cc:488` `shadowTracker.tick()`; Delay/DoM/STT gate on `isSpeculative()` (`lsq_unit.cc:194,1783,1787`) |
| amulet-InvisiSpec | `rob_impl.hh:421-470` (same rule as stt) | expose/validate when `isPrevBrsResolved()` in Spectre mode (`lsq_unit_impl.hh:1043,1073`) |
| amulet-CleanupSpec | `rob_impl.hh:420-471` | `lsq_unit_impl.hh:1247,1277`; cleanup on squash (SIMSPECT_HOOKS `cleanup_*`) |
| amulet-SpecLFB | `rob.cc:423-536`: control blocks while `!readyToCommit()`, except direct-unconditional (DOLMA rule, with an X86 mnemonic workaround) | `setPrevBrsResolved` → `clearCUSL` (`rob.cc:440ff`); `lsq_unit.cc:826` |

All of these key on `readyToCommit()` or `markCompletedInsts`, so **`visible_tick` = the `setCanCommit()` tick is the single cross-build resolution point.** Only the downstream VP/untaint/shadow-free logic differs, and it runs in the same commit tick (STT/SPT/InvisiSpec/CleanupSpec/recon) or at the next ROB update (SpecLFB).

### Error in today's estimate

| case | estimate vs truth |
|---|---|
| stall registered, ROB-VP defense | `prop_tick` = IEW release. Defense-visible resolution comes about 1 cycle later (`iewToCommitDelay`), so the gate is about 1 cycle too strict. |
| stall NOT registered (spt / recon-modded before alias, or any skipped entry) | Real resolution ≈ `complete` + 1 cycle, but the estimate says `complete + stall`. The gate is wrong by the whole stall, which can produce false in-window verdicts. |
| STT implicit-channel pending squash | Resolution (VP) is on time, but the redirect is deferred until untaint. `prop_tick` says nothing about the redirect (check_br already uses `parse_commit_squashes`). |
| branch squashed before release | The branch never resolves, but the estimate invents a `prop_tick`. |
| x86 macro-op with several micro-op records at the PC | `best_record` picks the latest-retiring record. If that is not the control micro-op, `complete` is the wrong micro-op's tick. |

## B2. Proposed print-only DPRINTF

Format follows `SIMSPECT_HOOKS.md`, so `parse_simspect_line` (`gem5_common.py:315-334`) parses it unchanged. Unknown keys come through as strings. `struct=BR`. Print with `DPRINTFR(O3PipeView, ...)`. `debug/O3PipeView.hh` is already included in the IEW and commit files of every build (checked).

**Site 1, IEW hook schedule** (just before `cpu->schedule(` — stt `iew_impl.hh:1342`, stt-dbg `:1342`, spt `:1384`, InvisiSpec `:1336`, CleanupSpec `:1435`, amulet-STT `:1341`, SpecLFB `iew.cc:1307`, recon-modded `iew.cc` scheduling block after line 1326):

```
DPRINTFR(O3PipeView, "O3PipeView:simspect:%llu:BR:resolve_hold:line=-:seq=%llu:pc=%#llx:victim=-:cause=-:sq=-:id=-:stall=%llu:fire=%llu:mispred=%d\n",
         (unsigned long long)curTick(), (unsigned long long)inst->seqNum,
         (unsigned long long)inst->pcState().instAddr(), (unsigned long long)stall,
         (unsigned long long)cpu->clockEdge(stall), (int)inst->mispredicted());
```

**Site 2, inside the lambda:** on the `isSquashed()` early return, print `resolve_drop` (same fields, without stall/fire). After `instToCommit(stall_inst)`, print `resolve_release` with `mispred=%d:bcast=%d`, where `bcast=1` iff `squashDueToBranch` was called (that is, the `fetchRedirect`/`squashedSeqNum` guard passed).

**Site 3, commit `markCompletedInsts`, right after `setCanCommit()`** (stt `commit_impl.hh:1600`, spt `:1709`, InvisiSpec `:1418`, CleanupSpec `:1434`, amulet-STT `:1600`, SpecLFB `commit.cc:1397`, recon-modded `commit.cc:1477`). For any `isControl()` inst, print `resolve_visible` with `ann=%d`, where `ann` = `cpu->getBranchPred()->getResolveStallCyclesFor(pc)>0`. The `getBranchPred()` accessor already exists in every hooked `cpu.hh`. Printing all control insts, not only annotated ones, gives a real resolution tick for un-stalled branches too, at negligible trace cost for litmus programs.

**Optional site 4 (STT/SPT/amulet-STT only):** print `resolve_pending` next to the existing `made pending` DPRINTF (`commit_impl.hh:934-953`). Print `resolve_squash` with `lazy=0|1` next to `Squashing due to branch mispred` (`:1041` / `:1113`). The Commit-flag text already carries both, so this is for uniformity only.

The output is print-only, so ticks and the non-simspect pipeview must stay identical to the pre-hook binary. Verify with the `gem5-hooks/verify/verify_simspect_hooks.py` pattern used on 2026-10-28.

### gem5_common changes (proposal, not made)

- `parse_branch_resolutions(trace) -> {pc: {seq: {hold, fire, stall, release, drop, visible, bcast, mispred}}}`, built from `parse_simspect_events` with `struct == "BR"` (values cast to int).
- `check_branch_resolutions(..., br_events=None)`: for each annotated `u`, pick the dynamic instance that has a `hold`. Prefer the non-dropped one with the largest seq. Set `resolve_tick = visible or release`, and `ok = xmit_complete < resolve_tick`. If there is a `hold` but neither a release nor a visible event (dropped, or the sim ended first), treat the branch as never resolved. Then:
  - When `stall>0` but no `hold` exists, set `stall_applied=False` and mark the record `status="warn"` with "resolve stall not registered (annotation key?)". This would have caught the spt/recon-modded key bug automatically.
  - When the binary emits no BR lines at all, fall back to today's estimate and tag `br_resolve_source="estimate"`.
- New per-record fields: `br_resolve_source` (`observed`|`estimate`), and per branch `hold_tick`, `fire_tick`, `release_tick`, `visible_tick`, `squash_tick` (from `parse_commit_squashes`), `estimate_tick`, `stall_applied`, `delta_visible_minus_estimate`.
- **Zero-rebuild stopgap:** parse the Commit line `<tick>: system.cpu.commit: [tid:0]: Marking PC (<pc>=>...).(u=>u), [sn:N] ready within ROB.` (stt `commit_impl.hh:1593-1597`; recon wording `[tid:%i] Marking PC`). It gives `visible_tick` per sn on every build today. `visible - complete ≈ stall*tpc + 1 cycle` means the stall was applied, and `≈ 1 cycle` means it was not.

## C. Feasibility per build

| build | add RS hook? | add BR DPRINTF? | files | effort / blockers |
|---|---|---|---|---|
| gem5-recon-modded | already has it | yes | `src/cpu/o3/iew.cc`, `commit.cc` | low. gem5 22, py3 scons. Could alternatively enable the `IEW` flag for the existing `[ResolveStall] FIRING` line, but that makes the trace far bigger. No git, so re-capture `recon-modded_src.diff`. |
| gem5-recon | **no** (it is the un-hooked control) | only `resolve_visible` (site 3) if wanted | `commit.cc` | low, but it changes the control binary. Recommend leaving it alone. |
| stt, stt-dbg | already | yes | `iew_impl.hh`, `commit_impl.hh` | low. py2 scons 2.5.1 (`build_simspect_hooks.sh` pattern). Git-tracked, so re-capture `gem5-hooks/<build>/<build>.patch`. |
| gem5-spt | already | yes | same | low. Ruby `X86_MESI_Two_Level` makes the rebuild longer (SLICC), but the O3 files are unaffected. Re-capture the patch. |
| amulet InvisiSpec / CleanupSpec | already | yes | same | low. py2, Ruby. No git: diff against `/work/amulet/backups/*-pre-simspect-hooks-20261028.tgz` and keep a `.pre-*` binary. |
| amulet SpecLFB | already | yes | `iew.cc`, `commit.cc` | low. py3 (`SCONS_LIB_DIR= python3 /usr/bin/scons`). |
| amulet STT | already | yes | `iew_impl.hh`, `commit_impl.hh` | low. Fix the stale registry entry. |
| sdo | no (never instrumented) | n/a until hooked | full 9-site port from `gem5-hooks/stt/stt.patch` | medium. Same cwfletcher lineage as stt, but no `build/` exists (first build) and its scope is undecided (`specs/gem5_builds.json`). |

General blockers: a rebuild overwrites `build/<ISA>/gem5.opt` in place, which would change the binary under any running campaign. Copy the binary to `.pre-resolution-hooks-<date>` first and rebuild only while nothing is running. This is a gem5-source change, even though it is print-only, so it needs Anna's sign-off under CLAUDE.md "hooks only". `wiki/design/COMMIT_BOUNDARY.md`, cited by `gem5_common.py:165`, does not exist yet.

## Open questions for Anna

1. Which tick should gate "branch still unresolved": `visible_tick` (the defense's VP, recommended) or `release_tick` (IEW)? The two differ by about 1 cycle on all builds.
2. Should the spt and recon-modded campaigns run before the `_branch_ann_for_se` alias be marked as run without BTB force or stall (registry + `hit_categories.json`)?
3. Approve adding the BR DPRINTFs to the 8 hooked builds (print-only), and a rebuild window?
