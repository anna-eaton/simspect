# Resolve-hooks code audit (2026-10-30 patch, 8 builds)

Adversarial, read-only review of the 2026-10-30 resolve-hooks patch (`gem5-hooks/resolve/apply_resolve_hooks.py`, applied diffs `gem5-hooks/<build>/resolve_hooks.diff`). I checked it against the live source in the cafe2 `gem5_dev` container under `/work/...`, copied read-only with `tar` on 2026-10-30. Every `file:line` below is a path relative to that build's root on cafe2 (for example `/work/stt/src/cpu/pred/bpred_unit.cc:329`). I did not run, rebuild or edit anything. The only "evidence run" was a small read-only Python scan of existing `/tmp/hookaudit_inst-*/*/m5out/trace.txt` files on cafe2. The temporary script was deleted afterwards.

## Verdict up front

- **The patch does what it claims.** Edits (2) and (3) only print. Edit (1) changes behaviour only when the forced target is 1. On every build, the force-not-taken code uses exactly the fall-through computation that the build's own not-taken path uses. It runs before `pc`, `predict_record.target` (gem5-22) and the push to `predHist` are set, so all of those see the overridden values. All 8 live trees carry the marker in all 3 files, with 6 hook print sites each.
- **ISSUE (older than this patch, and it matters for timing): the deferred `stallBcast` lambda never wakes the CPU.** None of the 8 lambdas calls `cpu->wakeCPU()` or `cpu->activityThisCycle()`. If the O3 CPU goes idle while a branch is held (the activity recorder decays and the tick event is not rescheduled), the release event still fires at `fire`. But the branch then sits in the IEW→commit time buffer until something else wakes the CPU. So the branch resolves to the defense later than the configured stall, by an amount that is not controlled. The trace evidence and source are below. The new `resolve_visible` line is what makes this visible. Any checker that uses `fire` or `resolve_release` as the resolution time is wrong in these cases, and one that uses `resolve_visible` is right.
- **The coordinator's extra question is answered "no".** The 19–40-cycle delay before "A incoming squash … can be resolved now" is **not** STT's implicit-channel pending-squash path. That message is printed only by `handleSquashSignalFromIEW`. That is the immediate (untainted, or implicit channel off) path. The pending path prints different messages. Commit's `setCanCommit()` is not gated by squash or taint logic at all. The delay is the CPU-idle side effect of the hook described above.
- **RISKs (minor):**
  - The force-not-taken override, like the existing forced-taken one, does not repair the direction predictor's speculative global history. This changes later predictions slightly but is not a correctness problem.
  - `updateExeInstStats` stamps the branch's pipeview `complete` tick at execute time, before the hold.
  - The stale `wbCycle` value can push a release one cycle later.
  - A held branch could hang the simulation if nothing ever wakes the CPU.

## Verdict table

| build | (1) force-NT correctness | (2) print safety | (3) stall gates all resolution consumers | fnc stall placement | CPU-wake on release |
|---|---|---|---|---|---|
| stt | OK (RISK: GHR not repaired) | OK | OK | OK | ISSUE |
| stt-dbg | OK (same) | OK | OK | OK | ISSUE |
| gem5-spt | OK (same) | OK | OK | OK | ISSUE |
| amulet-InvisiSpec | OK (same) | OK | OK | OK | ISSUE |
| amulet-CleanupSpec | OK (same) | OK | OK | OK | ISSUE |
| amulet-STT | OK (same) | OK | OK | OK | ISSUE |
| amulet-SpecLFB (gem5-22) | OK (same) | OK | OK | OK | ISSUE |
| gem5-recon-modded (gem5-22) | OK (same) | OK | OK | OK | ISSUE |

"(3) OK" means every defense-visible notion of "branch resolved" that I found comes from `readyToCommit()`/`setCanCommit()` in commit `markCompletedInsts` (plus recon's `branchResolved(true)`, which is set at the same place). That happens only after the lambda's `instToCommit`. The CPU-wake column is separate: it says *when* that release actually reaches commit.

## 1. Force-not-taken in `BPredUnit::predict`

### Old template trees (stt, stt-dbg, gem5-spt, amulet InvisiSpec/CleanupSpec/STT)

- In `stt/src/cpu/pred/bpred_unit.cc:197`, `target` is a `TheISA::PCState` (`TheISA::PCState target = pc;`). The new code is `target = pc; TheISA::advancePC(target, inst);` (`:330-331`). This is identical to the build's own not-taken paths: direction says not-taken at `:321`, BTB miss at `:288`, indirect miss at `:311`. `pc` has not been changed yet at that point (`pc = target;` is at `:348`), so the code advances from the real branch PC. For x86 this advances past the last micro-op to the next macro-op, the same as the natural fall-through.
- `pred_taken`/`predict_record.predTaken` are set to false (`:332-333`) before `pc = target` (`:348`) and before `predHist[tid].push_front(predict_record)` (`:350`). The old `PredictorHistory` has no `target` field, so there is nothing else to set. The function's return value, which fetch stores as `predTaken`, is false, and fetch's `predTarg` is the fall-through. So `mispredicted()` and the IEW `readPredTaken()` statistics are consistent.
- **When direction said taken (BTB hit) and we override to not-taken:**
  - RAS: for a call, `RAS[tid].push(pc)` (`:250`) stays pushed with `pushedRAS=wasCall=true`. A call is always actually taken, so the mispredict squash path keeps it, which is correct. For a return, the RAS was popped with `usedRAS=true`. On the mispredict (actually taken), nothing more is popped, which is correct. Litmus annotations only force conditional `jcc`, so this is theoretical anyway.
  - Direction-predictor history (RISK, low): `bp_history` was built by `lookup()` with "taken". The natural BTB-miss path fixes this by calling `btbUpdate(tid, pc, bp_history)` (`:281`), but the override does not. If the branch really is not-taken (no squash), the speculative global history keeps a "taken" bit until a later squash. At commit, `update(..., predTaken=false, bp_history, false)` trains the counters correctly. This only affects later *predictions* of other branches. The existing forced-taken override has the mirror-image flaw. Fix if wanted: call `btbUpdate(tid, pc.instAddr(), bp_history)` in the target==1 branch when `!inst->isCall() && !inst->isReturn()` and the original prediction was taken.
  - If actually taken (a real mispredict from our forced not-taken), `BPredUnit::squash(sn, corrTarget, actually_taken, tid)` (`:414`) sets `predTaken = actually_taken` (`:477`) and calls `update(..., squashed=true)`, which repairs the history. There is no `bp_history` mismatch assert in this path.
- Sentinel safety: the constructor only registers forced targets when `tgt != 0` (`stt/src/cpu/pred/bpred_unit.cc:84`, and the same in the other old trees at `:84`/`:85`/`:87`). Values 0 (stall only) and 1 (not-taken) can never collide with a real target PC.
- Decode early-resolve: `stt/src/cpu/o3/decode_impl.hh:724-735` only checks direct control that is unconditional or predicted taken. A forced-not-taken conditional branch is therefore not resolved early in decode, and its mispredict is found at execute, as intended.

### gem5-22 trees (gem5-recon-modded, amulet-SpecLFB)

- `target` is a `std::unique_ptr<PCStateBase>` (`gem5-recon-modded/src/cpu/pred/bpred_unit.cc:185`). `target.reset(pc.clone()); inst->advancePC(*target);` (`:341-342`) is the same as the natural not-taken path at `:323` (BTB miss `:286`, indirect miss `:313`). The same holds in SpecLFB at `amulet-gem5-SpecLFB_AE-v1.1/src/cpu/pred/bpred_unit.cc:304-305` and `:297`.
- Order is correct. The override (recon `:340-357`, SpecLFB `:303-320`) runs before `predict_record.target = target->instAddr();` (recon `:359`, SpecLFB `:322`) and before `set(pc, *target);` (`:361`/`:324`). So the stored target is the fall-through, and the commit-time `update(..., predTaken, ..., target)` and squash-time fixups see the overridden values.
- `iPred->updateDirectionInfo(tid, orig_pred_taken)` (`:369`/`:332`) uses the original direction on purpose (upstream comment). This matches how the existing forced-taken override behaves. It only matters for indirect branches.
- The same GHR-not-repaired RISK applies (`btbUpdate` at recon `:277`, SpecLFB `:251` is not called by the override).
- Build difference in the taken branch: recon uses `target->setInstAddr(forced)` and SpecLFB uses `target->as<X86ISA::PCState>().set(it->second)`. These are equivalent because `UPCState::setInstAddr` is `set(val)` (`/work/gem5-recon-modded/src/arch/generic/pcstate.hh:427`). Not a material difference.
- Cosmetic: recon's existing `DPRINTF(Branch, "...forcing BTB target ... to %#x")` will print `0x1` for not-taken forces.

## 2. Print safety

- Every argument is cast explicitly to match its specifier: `%llu`↔`(unsigned long long)`, `%#llx`↔`(unsigned long long)`, `%d`↔`(int)`. The argument counts match: predict_force 5, hold 6, drop 3, release 4, bcast 3, visible 6 (see the diffs, for example `gem5-hooks/stt/resolve_hooks.diff`).
- `mispredicted()` is a pure function with no side effects: old `stt/src/cpu/base_dyn_inst.hh:642-647` (copy pc, advance, compare), gem5-22 `gem5-recon-modded/src/cpu/o3/dyn_inst.hh:562-567` (clone, advance, compare). At `resolve_hold` it runs after `inst->execute()` (`stt/src/cpu/o3/iew_impl.hh:1328-1331`), so the value is meaningful. The one exception is an instruction that faulted earlier, where `execute()` is skipped; the printed `mispred` is then meaningless, but this is harmless.
- `getBranchPred()` is public on the CPU (`stt/src/cpu/o3/cpu.hh:718`, `gem5-recon-modded/src/cpu/o3/cpu.hh:597`, `amulet-gem5-SpecLFB_AE-v1.1/src/cpu/o3/cpu.hh:521`). `getResolveStallCyclesFor` is a public const map lookup (`stt/src/cpu/pred/bpred_unit.hh:308-311`, `gem5-recon-modded/src/cpu/pred/bpred_unit.hh:319-324`). Neither has side effects.
- `pcState().microPC()` exists for x86 PC states, and all builds compiled (rc=0). `cpu->clockEdge(stall)` is const. `bpred_unit.cc` adds `debug/O3PipeView.hh` and `sim/core.hh`. InvisiSpec already included `sim/core.hh`, so the duplicate include is harmless.
- Log volume: `resolve_visible` fires for **every** control micro-op that reaches commit, not only annotated ones. This is fine, but parsers must filter by `stall>0` or by PC.

## 3. Does the stall gate resolution?

The hook is at the same place in all 8 builds: right after `inst->execute()` in `executeInsts`. For a control instruction whose PC has a stall, it skips `setExecuted()`, `instToCommit()` and the mispredict check, and schedules a lambda that does them at `clockEdge(stall)`. Locations: `stt/src/cpu/o3/iew_impl.hh:1335-1381`, `stt-dbg` same lines, `gem5-spt/src/cpu/o3/iew_impl.hh:1377-1423`, `amulet-gem5-InvisiSpec_AE-v1.1/src/cpu/o3/iew_impl.hh:1330-1375`, `amulet-gem5-CleanupSpec_AE-v1.1/src/cpu/o3/iew_impl.hh:1429-1474`, `amulet-gem5-STT_AE-v1.1/src/cpu/o3/iew_impl.hh:1335-1380`, `amulet-gem5-SpecLFB_AE-v1.1/src/cpu/o3/iew.cc:1301-1346`, `gem5-recon-modded/src/cpu/o3/iew.cc:1309-1387`.

What the lambda delays: `setExecuted()`; `instToCommit()`, which leads to IEW `writebackInsts` and then commit `markCompletedInsts` → `setCanCommit()`; and the mispredict `squashDueToBranch`. That squash leads to commit squash handling, then fetch `branchPred->squash(...)`. The commit-time `BPredUnit::update` cannot run past the branch either, because the branch cannot commit before `canCommit`.

How each defense decides a branch is resolved, and whether that is gated:

- **STT (stt, stt-dbg, amulet-STT):** `ROB::updateVisibleState` clears `prevBrsResolved` when a control instruction is `!readyToCommit()` (`stt/src/cpu/o3/rob_impl.hh:489-495`). That drives `isUnsquashable` (`:517-531`), which drives taint (`compute_taint`: an access instruction that is not unsquashable has its destination tainted, `:808-812`) and LSQ `readyToExpose` (`stt/src/cpu/o3/lsq_unit_impl.hh:1018,1051`). These functions are called from `markCompletedInsts` after `setCanCommit` (`stt/src/cpu/o3/commit_impl.hh:1617-1622`). Implicit-channel squash delay uses `isArgsTainted` of the branch (`:934-955`) and is downstream of the release. **Gated.**
- **SPT (gem5-spt):** the same `readyToCommit` → `prevBrsResolved` → `isUnsquashable` → `propagateUntaint` chain (`gem5-spt/src/cpu/o3/rob_impl.hh:533-575`), called at `gem5-spt/src/cpu/o3/commit_impl.hh:1727`. **Gated.**
- **InvisiSpec / CleanupSpec (amulet):** `prevBrsResolved` is cleared on a control instruction that is `!readyToCommit()` (`amulet-gem5-InvisiSpec_AE-v1.1/src/cpu/o3/rob_impl.hh:465-471`, `amulet-gem5-CleanupSpec_AE-v1.1/src/cpu/o3/rob_impl.hh:465-471`). That feeds `readyToExpose` (`amulet-gem5-CleanupSpec_AE-v1.1/src/cpu/o3/lsq_unit_impl.hh:1277`). **Gated.**
- **SpecLFB:** `ROB::updateSafeState` clears `prevBrsResolved` on a control instruction that is `!readyToCommit()` (`amulet-gem5-SpecLFB_AE-v1.1/src/cpu/o3/rob.cc:497-501`). This clears CUSL/USL marks (`:438-447`) and is called after `markCompletedInsts` (`commit.cc:1411-1414`). **Gated.**
- **Recon (gem5-recon-modded):** `branchResolved(true)` is set only in `markCompletedInsts` right after `setCanCommit` (`gem5-recon-modded/src/cpu/o3/commit.cc:1488-1490`). `ShadowTracker::freeBranches` drops a branch only once it is `branchResolved()` (`secure_scheme/shadow_tracker.cc` `freeBranches`). The delay unit and IQ use `getOldestBranchShadow()` (`secure_scheme/delay_unit.cc:140`, `inst_queue.cc:1462`). **Gated.**

What is *not* gated, and its effect:

- `inst->execute()` runs immediately, so the branch's architectural outcome is computed early. No defense reads it before `canCommit`.
- `updateExeInstStats(inst)` runs at hold time (`stt/src/cpu/o3/iew_impl.hh:1379`). It also sets the pipeview `completeTick` (`:1686-1688`). The branch's pipeview `complete` tick is therefore the pre-stall execute time (RISK for any checker that uses it as "resolved"; use `resolve_visible`).
- The lambda's `fetchRedirect`/`toCommit` check reads per-cycle state left over from the last IEW tick. This is safe because `squashDueToBranch` keeps the older squash (`stt/src/cpu/o3/iew_impl.hh:487-488`).
- `wbCycle`/`wbNumInst` are reset only at the start of IEW `tick` (`:1547-1548`). If the previous cycle wrote more than `wbWidth` instructions back, `instToCommit` (`:621-633`) can put the released branch one slot later (RISK, at most 1–2 cycles).

### ISSUE: the release does not wake an idle CPU (all 8 builds)

- The CPU tick only reschedules itself while `activityRec.active()` (old trees: the `FullO3CPU<Impl>::tick` tail at `stt/src/cpu/o3/cpu.cc:642-652`; `gem5-recon-modded/src/cpu/o3/cpu.cc:517`; `amulet-gem5-SpecLFB_AE-v1.1/src/cpu/o3/cpu.cc:491`). The only way back is `wakeCPU()` (`stt/src/cpu/o3/cpu.cc:1812-1830`) or activity from somewhere else.
- None of the 8 stall lambdas (from the `resolve_hold` site to the end of the lambda) contains `wakeCPU` or `activityThisCycle`. I checked this with grep over the live sources.
- **Trace proof:** `/tmp/hookaudit_inst-098607_5od15dt2/ann_S/m5out/trace.txt` on cafe2 (an STT build with `STT=true implicitChannel=true`, from its `config.ini`). The `Commit` debug flag prints `tick() begins` on every CPU tick.
  - Hold at 2953500, `fire=3053500`.
  - The last commit tick before the release is at 3018000. There are no commit ticks at all from 3018000 to 3069000: the CPU was idle for about 100 cycles.
  - `resolve_release` and `resolve_bcast` print at 3053500, inside that idle stretch.
  - The CPU next ticks at 3069000. At 3069500 commit prints "A incoming squash [sn:601] … can be resolved now", then "Marking … [sn:601] ready within ROB", then `resolve_visible … stall=200`.
  - So the branch became defense-visible 16000 ticks, or 32 cycles at 500 ticks/cycle, after the configured release.
- **How often:** across 392 `hookaudit` dirs, 335 release/visible lines were parsed. 303 pairs had the normal 1-cycle gap (500 ticks). 28 pairs had 27–40-cycle gaps (13500–20000 ticks). 4 releases had no `resolve_visible` (squashed or the run ended). All gapped samples whose config I checked are STT with the implicit channel on. Other builds were not sampled here, but they have the same lambda.
- What woke the CPU at 3069000 is not visible, because `Activity`/`O3CPU` flags were not on. A returning memory response is the likely cause (unverified). If nothing ever wakes the CPU, the held branch would never resolve.
- Suggested hook fix, to be approved by Anna and followed by a rebuild: at the top of each lambda (before the `isSquashed` check), add `cpu->wakeCPU(); cpu->activityThisCycle();`. This would make the effective stall equal the configured stall. It does change behaviour, so treat it as a hook change and re-run `hook_audit`.

### Coordinator's question: is the 19–40-cycle "A incoming squash" delay STT's pending-squash path?

**No.** The message "A incoming squash [sn:%lli,…] PC %s can be resolved now" exists only in `DefaultCommit::handleSquashSignalFromIEW` (`stt/src/cpu/o3/commit_impl.hh:1035`; also `stt-dbg:1035`, `gem5-spt:1045`, `amulet-STT:1035`). That function is the immediate path. It is called when the implicit channel is off (`:911-912`) or when `instCausingSquash` is **not** tainted (`:954-955`).

The implicit-channel pending path is different:

- It prints "(Lazy) A branch mispredicInst … is made pending." and sets `hasPendingSquash(true)` (`:936-952`).
- Later, when the branch is untainted, `getResolvedPendingSquashInst` (`stt/src/cpu/o3/rob_impl.hh:889-900`) triggers `handleSquashSignalFromROB`. That prints "(Lazy enabled) A pending squash … can be resolved now" (`commit_impl.hh:1103`).

`setCanCommit()` is not tied to any of this. `markCompletedInsts()` (`:728`) runs every commit tick right after `commit()` (`:726`), regardless of squash or taint state. It marks the branch ready in the same tick its time-buffer slot arrives. That slot also carries the IEW squash signal, which is why the "A incoming" line and `resolve_visible` share a tick.

The trace confirms both cases:

- Tainted: in `/tmp/hookaudit_inst-027233_b2e9c41s/ann_S/m5out/trace.txt`, a tainted branch logs "(Lazy) … is made pending" and `resolve_visible` in the same tick (2952500).
- Untainted: in the same file, a held untainted branch releases at 3048500 and is visible at 3049000 (1 cycle), when the CPU was still ticking.

The 19–40-cycle cases are the CPU-idle issue above, which is a side effect of the hook, not STT semantics.

### fnc commit stall

`commitInsts` stalls the head when `head_inst->instAddr() == fncCommitStallPC` for `fncCommitStallCycles` calls (`stt/src/cpu/o3/commit_impl.hh:1207-1221`; `gem5-spt:1219-1232`; `gem5-recon-modded/src/cpu/o3/commit.cc:1005-1017`; `amulet-CleanupSpec:1042-1053`; `amulet-InvisiSpec:1038-1052`; `amulet-SpecLFB commit.cc:1004-1017`; `amulet-STT:1209-1221`). It is placed after `isHeadReady`, so it only counts once the head can commit. A ready head keeps commit `Active` (`stt/src/cpu/o3/commit_impl.hh:735-738`), so the CPU keeps ticking and the count is real cycles. Minor RISK: the key is the macro-op PC and the counter resets per `seqNum`. A multi-micro-op instruction at that PC therefore gets the stall once per micro-op. Squashed heads are exempt. This was not changed by the patch.

## 4. Differences between builds that matter

- The old trees and SpecLFB share the `[this, stall_inst, stall_tid]` lambda. Recon has its own `[this, inst, tid_local]` lambda (`gem5-recon-modded/src/cpu/o3/iew.cc:1340-1383`) and a dead commit-stall placeholder lambda (`:1389-1408`, `commitStallCycles` is always 0). The generator only edits code after the branch hook, so the placeholder was correctly left alone (the recon diff touches only the branch lambda).
- The not-taken computations differ only by gem5 API (`TheISA::advancePC` vs `inst->advancePC(*target)`). Each matches its own build's natural not-taken code.
- Recon additionally sets `branchResolved(true)` right after the new `resolve_visible` print (`commit.cc:1488-1490`). The print is only a print, so ordering does not matter.
- SpecLFB has `if(defense) rob->updateSafeState()` after `markCompletedInsts` (`commit.cc:1411-1414`). It is gated in the same way.
- No build differs in the CPU-wake gap. All 8 have it.

## Open / not verified

- What woke the CPU in the gapped traces (needs a `--debug-flags=Activity,O3CPU` rerun, which is out of scope for this read-only audit).
- I did not check whether the existing forced-taken x86 `PCState` survives decode's full-state comparison (`decode_impl.hh:729`). That is the existing taken path, not this patch.
