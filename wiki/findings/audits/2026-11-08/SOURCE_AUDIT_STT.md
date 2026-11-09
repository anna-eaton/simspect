# Source audit: upstream STT gem5 (cwfletcher/stt @ e3283b9), 2026-11-08 trial run (round 2)

This is a read-only manual audit of `~/trippel/defense_src/stt_e3283b9/src` (paths below are relative to `src/`). It checks the code against the inferred STT contract (`STT_6.als:325-332`, `specs/leakage/stt.json`) and against the paper (`~/Documents/quail/sources/papers/yu-2019-stt.pdf`, MICRO'19). Our config for `/work/stt` is X86 O3, SE mode, classic `--caches`, STT=1, threatModel=Spectre, implicitChannel=1, needsTSO=0, moreTransmitInsts=0 (`gem5-hooks/stt/se_exp.py:326-333`). Nothing was run in gem5; every finding comes from reading the code. Stock timing below means the O3CPU.py defaults: renameToROBDelay=1, renameToIEWDelay=2, issueToExecuteDelay=1, iewToCommitDelay=1, commitToIEWDelay=1.

## Summary (new findings)

| ID | Class | Confidence | Claim | Known? |
|---|---|---|---|---|
| S1 | A | confirmed by reading | Taint is never propagated through FP register index 16 (= the low half of XMM4). The "zero register" skip ignores register class, and no other register class collides with it. | new |
| S4 | A | confirmed by reading (schedule); reachability depends on dispatch timing. **gem5 check 2026-11-09: the predicted window did NOT open at the exact alignment (T still "Deferring load due to virtual fence" at N+1, both builds); reading claim needs revisit, see "S4 / A3 gem5 check"** **Trace follow-up 2026-11-09 (bug-investigate-s4trace): not a bug as described. `readyToCommit()` is false while a squash is pending (`base_dyn_inst.hh:964-968`), so B1 counts as unresolved and nothing past it is untainted until the pending squash is released; the release cycle is the A4 race (needs commitToIEWDelay ≥ 2, data at ≥ 3; see "S4 trace follow-up").** | At stock timing, a mispredicted branch with a tainted predicate opens a one-cycle window. When an older branch resolves, its wrong path is untainted one commit cycle before its delayed squash fires, so a wrong-path load issued in that cycle executes and reaches the cache. | new; same family as known A4, but A4 does not leak at stock timing |

Known, not counted: S2 and S3 from round 1 (the store-set training and memory-order squash on a tainted store address, and the store-to-load forwarding cases) are reclassified as **known: STT does not protect store addresses (Anna, 2026-11-08)**. In one line each: S2 is `iew_impl.hh:1393` plus `commit_impl.hh:936`; S3 is `lsq_unit.hh:733-868` plus `rob_impl.hh:733-734`. Also known: A3c (a younger squash is dropped when it lands in the same cycle as a tainted mispredict, `iew_impl.hh:1351-1414`) and KV3 (store TLB fill).

## S1. Taint dropped through XMM4 low (FP reg 16)

- **Code:** `cpu/o3/rob_impl.hh:229` in `insertInst`: `if (inst->srcRegIdx(i).index() == 16) // exclude zero register … continue;`. The check never looks at the class. `RegId::index()` is the index within its class (`cpu/reg_class.hh:164`).
- **The ISA confirms the collision:**
  - Integer 16 is `ZeroReg = NUM_INTREGS` (`arch/x86/registers.hh:82`, `regs/int.hh:149-158`, the microcode t0), so skipping it there is intended.
  - FP: `FLOATREG_XMM_BASE = FLOATREG_MMX_BASE + NumMMXRegs` with `NumMMXRegs = 8` (`regs/float.hh`, `x86_traits.hh:57`). XMM0_LOW is 8, XMM0_HIGH is 9, …, so **XMM4_LOW is 16**.
- **Other classes do not collide:**
  - CC has 5 registers (`regs/ccr.hh:49-55`).
  - x86 has `NumVecRegs = 1` (`registers.hh:104`).
  - Misc 16 is `MISCREG_DR0` (`regs/misc.hh:124-125`, `NumCRegs = 16`), a privileged debug register that our SE programs never touch, and misc registers are not renamed (`rename_impl.hh:1046`).
  - x87 stack registers are flattened from indices ≥ NUM_FLOATREGS, so they do not hit 16.
  - So the only real casualty is XMM4_LOW.
- **Mechanism:**
  1. A consumer of xmm4-low gets no argProducer for that source.
  2. `explicit_flow` (`rob_impl.hh:710-722`) taints only through argProducers, so the consumer stays untainted, and so does its output.
  3. A load that depends on it then gets `fenceDelay(false)` (`lsq_unit_impl.hh:1013`) and executes.
- **Contradicts:** the protection-set propagation clause, and paper §6.2 p6 (taint follows every register data flow out of an unsafe access).
- **Litmus:**
  1. A mispredicted, held branch.
  2. `movq xmm4,[rbx+rdi*8]`: an access load (`ldfp xmml`, `simd128/integer/data_transfer/move.py:44`).
  3. `movq rax,xmm4` (`mov2int reg, xmmlm`, `general_purpose/data_transfer/move.py:360`).
  4. `shl rax,6`.
  5. `mov rcx,[rsi+rax]`: this load leaks.
  6. Control: the same program with xmm3 should be held.
- **SimSpect:** cannot generate it today, because Stage 2 emits GPRs only. `check_ld` would detect it as is.

### S1 gem5 check (2026-11-08, fpr-fanout session): CONFIRMED, real STT bug

- **Result on `/work/stt`:** for 100 STT_6 load→load instances that STT holds, routing the access load's value through **xmm4 leaks 98/100**. Through **xmm3 it leaks 0/100**, and the **GPR baseline leaks 0/100**. Leaks are decided by check_ld's data-obtained gate; xmm4 in-window fates are reached_cache 90, store_forward 8, executed_no_packet 2 (the last 2 are not leaks).
- **gem5-recon-modded control:** GPR 10/100, xmm3 8/100, xmm4 8/100. Every xmm hit is also a GPR-baseline hit, so xmm4 adds nothing on recon. Recon is not proof either way (its own `flatIndex()==16` skip on physical destinations, R-SA-12).
- **How it was generated:** new opt-in Stage-2 FPR routing (`parsexml.py` pass 5 `fpr_cfg`, `specs/fanout/fpr.json`). The gadget is `movq %out,%xmmK; movq $0,%out; movq %xmmK,%out`; the zeroing is needed because `mov2int` also reads its integer destination. So SimSpect now generates S1 itself. Configs: the canonical fixed-latest configs verbatim except `testset_dir` / `results_name`.
- **Skip present in:** `/work/stt` `rob_impl.hh:229` and `/work/amulet/amulet-gem5-STT_AE-v1.1` `rob_impl.hh:230` (`srcRegIdx(i).index() == 16`). Not in gem5-recon(-modded), which instead has `taint_tracker.cc:59` `flatIndex() == 16` (R-SA-12).
- **Reportable:** the general FP-mode corpus (random xmm, no pinning) finds it: 12 of 100 sampled load→load tests hit on `/work/stt`, every one through xmm4. The full-corpus run is in flight (see the review).
- **Other STT builds (2026-11-09, bug-investigate-fp):** upstream STT master (`/work/stt-master`, E3) and AMuLeT's STT (E4) carry S1 too. In the fanout-v2 FP campaigns every fp-only hit has xmm4 on the transmitter path (E3 31/31, E4 97/97) and nothing without xmm4 hits (0/269, 0/802); renaming xmm4→xmm3 in 3 hit stems turns 3/3 hits into 0/3 on both builds. Details: [`stt_xmm4_taint_skip/README.md`](../../bug/stt_xmm4_taint_skip/README.md) 'Upstream STT master (E3) and AMuLeT's STT (E4) share S1'.
- **Review write-up (stems, commands, trace lines, mechanism, verdict):** [`wiki/findings/bug/stt_xmm4_taint_skip/README.md`](../../bug/stt_xmm4_taint_skip/README.md). This answers Q2 below with option (b) rather than a bugsynth gadget, since Anna approved the parsexml change.

## S4. One-cycle wrong-path window behind a delayed (pending) tainted-branch squash

- **Setup:**
  - B0 is an older branch, correctly predicted but slow.
  - L1 is a load after B0, so it is tainted while B0 is unresolved.
  - B1 is a branch on L1's value, so its predicate is tainted; it mispredicts.
  - Past B1, on the wrong path: L2 (untainted address, reads a secret), then T = load [f(L2)].
- **While B0 is unresolved:**
  - B1 executes, IEW signals the squash, and commit makes it *pending* because B1 `isArgsTainted()` (`commit_impl.hh:936-952`).
  - B1 is `readyToCommit`, so it already counts as resolved for younger instructions (`rob_impl.hh:487-495`). The wrong path past B1 still stays tainted, because B0 is unresolved.
  - T is deferred at execute (`iew_impl.hh:1260-1265`, `onlyWaitForFence`).
- **Schedule when B0 completes** (cycle N is the commit cycle in which commit marks B0 completed):
  - Commit tick order is `commit()` then `markCompletedInsts()` (`commit_impl.hh:726-728`).
  - In commit N, `commit()` checks for a pending squash whose branch is now untainted (`:964-969`) using the *old* taint, so B1 is still tainted and nothing fires.
  - Then `markCompletedInsts` sets B0 canCommit and runs `updateVisibleState`. B0 and B1 are both resolved, so L1 and L2 become unsquashable, and `compute_taint` untaints B1, L2 and T (`:1586-1596`, `rob_impl.hh:516-520, 808-814`).
  - IEW N+1 runs before commit N+1 (`cpu.cc:615-623`). `ldstQueue.updateVisibleState()` clears T's fenceDelay (`iew_impl.hh:1521`, `lsq_unit_impl.hh:1013`), then `executeInsts()` runs the loads issued in cycle N. IQ issue never checks fenceDelay; only execute does.
  - Commit N+1 is the first point where the pending squash fires (`handleSquashSignalFromROB`, `:1098-1160`).
  - IEW N+2 sees that squash first thing (`iew_impl.hh:784-795`) and squashes the IQ and LSQ before it executes anything.
- **Reachability:**
  - **Leaks:** a wrong-path load issued *in cycle N* executes in N+1 with an untainted address, sends a cache packet, and is squashed in N+2. "Issued in cycle N" means one of two things: it was dispatched in N with its operands ready (it was put in the ROB in N-1 because renameToROBDelay < renameToIEWDelay, so its taint was computed at the end of N), or it was woken in N.
  - **Does not leak:** a load that was already deferred is re-scheduled only in N+1 (`inst_queue_impl.hh:1214-1232`) and is squashed in N+2.
  - So the leak is reachable at stock timing, but only through a fresh issue in that exact cycle. While B1's squash is pending the front end keeps fetching the wrong path, so a new dispatch every cycle is plausible unless the ROB or IQ is full.
- **Contrast with known A4:** for an untainted mispredict, the IEW squash signal reaches commit in the same cycle as the branch's completion, and `commit()` handles it before `markCompletedInsts` untaints anything. That is why A4 needs commitToIEWDelay ≥ 2-3. The pending path adds exactly one commit cycle.
- **Contradicts:** paper §6.4.1 p7, "Resolution-based channels are eliminated by delaying the effects of branch resolution until the branch's predicate becomes untainted". The code treats B1 as resolved (`readyToCommit`) the moment it executes. Also §6.1 p5, which says the visibility point requires all older control-flow to be resolved; a wrong-path instruction should never pass it.
- **Litmus:**
  1. `cmp [slow],0; jne L` (B0, correct, held).
  2. `mov rax,[rbx]` (L1).
  3. `test rax,rax; jz W` (B1, trained to mispredict).
  4. At W: `mov rdx,[rsi+rdi]` (L2, reads the secret).
  5. `shl rdx,6; mov rcx,[probe+rdx]` (T). T must be dispatched in the cycle B0's completion reaches commit, so vary the instruction count or an `imul` chain between L2 and T to sweep that cycle.
- **SimSpect:**
  - **Generation:** unclear and probably not today. A tainted unresolved branch is itself a `Branchxs.inreg` transmitter shape, and DESIGN.md notes that STT_6 transmitter branches are always resolved (compare the STT-2 "mispredicted xmit branch" proposal, `URGENT_TODO.md:135`).
  - **Detection:** `check_ld` would see T `reached_cache` in the window, and `diag_stt_vp_squash_race.py` would likely bucket it as A4. Its bug .md should note this stock-timing variant.
  - **Hook interaction:** SimSpect's resolve-stall release fires `instToCommit` for B0 from an event (`gem5-hooks/stt/resolve_hooks.diff:21-60`). That only changes when cycle N happens, not the logic.

## S4 / A3 gem5 check (2026-11-09, bug-investigate-stt-a3s4)

**Bottom line.** S4: not reached, and the mechanism this audit predicted did not reproduce. At the exact predicted alignment (T issued in the commit cycle N where B0 completes), T is still deferred at N+1 on both `/work/stt-master` and `/work/stt`. A3: A3a/A3b have nothing observable to hit; A3c is fixed on stt-master (E3) and blocked on a model decision plus a non-differential detector. Found by us: no, for both. Scratch on cafe2: `/tests/simspect_alloy_20261108/bugwork/stt_a3s4/` (56 MB, nothing running, no `/tmp` dirs because TMPDIR was set inside bugwork).

- **Stage 2 can now build the S4 shape.** I re-concretized the 50 `STT_6_s4` draft XMLs (s4-variant, 2026-11-08) with the cafe2 snapshot `code_20261109` and E3's exact Stage-2 options (`runconfigs/twostage_fv2_20261109/E3_STT_6_fv2.jsonc`: `fv2_vocab`, `fanout_v2`, `branch_cond.from_alloy`, per-branch stalls). Config copy: `bugwork/stt_a3s4/cfg_E3_stt_master.jsonc` (only paths, `sample_fraction` and jobs changed). Checker: `bugwork/stt_a3s4/s4_shape_check.py`.
  - B1 reads L1 in 50/50 tests per mode. Example `inst-000002`: L1 at pc2 is `movq 0x8(%r10),%r8`; B1 at pc3 is `movq %r8,%rax; andq $0,%rax; orq $1,%rax; cmpq $1,%rax; jae`. The 2026-11-08 blocker (B1's condition was an immediate) is gone.
  - B0 stays a stallable conditional branch in only 20/50 tests. In the other 30, `fv2_vocab`'s `jmp_direct: 0.5` turns B0 into a direct `jmp`.
  - The `STT_6_a3c` draft concretizes too (its B1 is the transmitter branch; 0 S4 shapes, as expected).
- **E3 verbatim: 0 hits out of 100** (50 tests × 2 modes, 3 grid points) on both `stt-master` and `/work/stt`. It cannot fire by construction. E3 stalls the resolved B0 by 0, 500 or 2500 cycles and the unresolved B1 by 2500, 5000 or 10000. So B0 always resolves first, B1 is untainted when it executes, and no squash is ever held pending.
- **Targeted probe in S4 order** (`bugwork/stt_a3s4/s4_probe.py`): same binary, se.py, flags and branch forcing as E3 (env built by `pipeline._build_gem5_env`). B1's stall is 0 and B0's stall is swept from 0 to 199 cycles in steps of 1, on 3 stems (`inst-000002`, `-000027`, `-000414`, `mispredict_not_taken`), with `check_ld --out` per point. That is 600 runs per build. On both builds T never executed. Up to a stall of about 111-113 cycles T has no LSQ record at all, because the wrong path is never fetched before B1's squash. Above that, T is `never_executed`. Results: `probe_master/` and `probe_old/` `probe_results.json`.
- **What the traces show** (kept: `bugwork/stt_a3s4/traces/master_inst-000002_b0s{150,120}_iewiq/`, flags O3PipeView+LSQUnit+IEW+IQ):
  - The pending-squash leg happens. B1 (sn:585) executes with `mispred=1` at tick 2955000 while B0 (sn:569) is held. Its squash fires one commit cycle after B0's `resolve_visible`: `(Lazy enabled) A pending squash [sn:585] ... can be resolved now`.
  - The wrong path arrives only ~115 cycles after B1. Its ROB insert is at 3005500; the next I-cache line is 0x401c80. So B0's stall must be at least ~113 cycles for T to exist at all.
  - Stall 150: T (sn:591) issues at 3009000 and logs `Deferring load due to virtual fence` at 3009500. B0 is visible at 3024000, the squash fires at 3024500, and T is squashed at 3025000. This is the "already deferred, no leak" case above.
  - Stall 120 is the exact predicted alignment: B0's `resolve_visible` (commit N) is at 3009000, the same tick T issues. At N+1 (3009500) IEW still logs `Deferring load due to virtual fence` for T. The pending squash fires in commit 3009500 and T is squashed at 3010000. No packet.
  - By reading, commit N's `markCompletedInsts → rob->updateVisibleState → compute_taint` (`commit_impl.hh:1585-1622`) should untaint T before IEW N+1's `ldstQueue.updateVisibleState()` (`iew_impl.hh:1574`; `:1599` on master). It did not. **Why is not pinned down.** The "dispatched in N with operands ready" path was not exercised either, because in this shape T always waits on L2.
- **Checker gap (would hide S4 even if it fired):** `check_ld` counts B1 as resolved at `resolve_visible` (= `setCanCommit` at execute, `gem5_common.check_branch_resolutions`) and bounds the window by fnc's retire (here fnc = B0). An S4 packet at N+1 falls after both. A single-trace fix: end a mispredicted branch's window at its squash tick (Anna's 2026-11-08 rule: executed but not yet squashed = unresolved). The probe used `cache_fate` directly, which is also single-trace: any T packet is a leak here, because T is always on B1's wrong path.
- **A3a/A3b:** the delay that the paper prescribes (§6.4.1 p7) is the pending squash, and it works for an explicitly tainted B1 (the trace line above). `hasImplicitFlow` being unused (`rob_impl.hh:809`) is dead code with no observable leak to hit (see the note on A3a/A3b below). **Verdict: nothing to reach.**
- **A3c:** fixed in stt-master (`18e304f`), so only `/work/stt` (e3283b9) can show it. Reaching it takes three things:
  - B2's squash must land in the same IEW cycle as the tainted B1's mispredict. This needs a dense per-branch sweep of B2's stall. `unresolved_stall_per_branch` mode `sweep` exists; B1, as the transmitter, is forced to stall 0 by `_inject_stalls`.
  - A detector that is not differential (Anna, 2026-11-08 21:15). Candidate: a single-trace invariant, "a younger untainted mispredicted branch executed (`resolve_visible mispred=1`) but its squash never fired before the older tainted branch's pending squash", read from the BR lines plus the commit squash lines. That detects the mechanism, not a cache leak.
  - A generator. The A3c draft is a design probe only.
  **Verdict: blocked on a model decision and a detector decision.**

**What it would take (S4), tied to Anna's minimality / bounded-enumeration direction:**

1. **First** explain why N+1 is still deferred: a short reading of the IEW and commit timebuffer order on stt-master, or one more traced run with ROB taint printing. Otherwise S4 may not exist as described.
2. **Model** (Anna rejected a cherry-picked exemption as production). Options:
   - (a) A cleverer minimality that keeps a resolved older boundary branch when it gates the taint of a younger unresolved branch's predicate.
   - (b) Bounded random enumeration without boundary minimality. S4 instances are ≥ 20,000 in the 6-instruction scope (`ALLOY_MODEL_CHANGES.md` q1/q3).
   - (c) A Stage-2 splice of B0+L1 in front of the window-opening branch, validated by the post-hoc checker (`ALLOY_MODEL_CHANGES.md:1554`).
3. **Stage 2:** done (`branch_cond.from_alloy`). Keep `jmp_direct` off for B0, or accept losing half the tests.
4. **Harness:** existing keys only. B1 stall 0 (`unresolved_stall_cycles: 0`, no per-branch choices) and a dense B0 `sweep.points` starting at the wrong-path fetch delay (≥ ~113 cycles here).
5. **Checker:** end the window at the mispredicted branch's squash tick, as in the checker-gap bullet above.

## S4 trace follow-up (2026-11-09, bug-investigate-s4trace)

**Verdict: S4 is not a bug as described. At stock timing no stall alignment opens the window. The audit's premise is wrong: B1 does *not* count as resolved while its squash is pending. What remains of the S4 shape is the known A4 race, fired at the cycle the pending squash is released, and it needs commitToIEWDelay ≥ 2 like A4.** Found by us: no (S4 at stock timing does not exist; the demo below uses a non-stock delay). Scratch on cafe2: `/tests/simspect_alloy_20261108/bugwork/stt_s4trace/` (856 KB, nothing running, TMPDIR inside it, no temp dirs left).

- **Why T is still deferred at N+1 (by reading; e3283b9 and stt-master are identical here).**
  - STT changed `readyToCommit()` to `status[CanCommit] && (!HasPendingSquash || Squashed)` (`src/cpu/base_dyn_inst.hh:964-968`, same on `/work/stt-master`). A branch whose squash is held is therefore *not* `readyToCommit`, even though it executed and has `CanCommit` set.
  - `ROB::updateVisibleState` sets `prevBrsResolved = false` at any control inst that is not `readyToCommit` (`src/cpu/o3/rob_impl.hh:489-493`). So everything younger than a pending B1 (L2, the negs, T) stays `!isPrevBrsResolved` → `!isUnsquashable` (`:516-522`), and `compute_taint` keeps L2's dest tainted (`:812-813`) and so T's args (`explicit_flow`, `:709-724`).
  - At commit N (B0's `resolve_visible`, 3009000 in `traces/master_inst-000002_b0s120_iewiq`), B0 becomes resolved. That untaints L1 and so B1's predicate, but **not** B1's wrong path. The audit's line "B1 is `readyToCommit`, so it already counts as resolved for younger instructions (`rob_impl.hh:487-495`)" missed the `HasPendingSquash` term. IEW N+1 then sets `fenceDelay = isArgsTainted` = true for T (`lsq_unit_impl.hh:1013`), which is exactly the `Deferring load due to virtual fence` at 3009500.
- **The only cycle in which B1's wrong path is untainted is the release cycle R (= N+1).** Commit R's `commit()` sees B1 untainted, clears `hasPendingSquash` and calls `handleSquashSignalFromROB` (`commit_impl.hh:964-969`). `ROB::squash` marks only `squashWidth` = 8 youngest insts squashed per cycle (`rob_impl.hh:381-385`, `O3CPU.py:112`); in this trace the ROB holds 81 insts, so L2 and T are not marked yet. The same tick's `markCompletedInsts` → `updateVisibleState` now sees B1 `readyToCommit` and untaints them. This is A4's mechanism exactly (a mispredicted branch counts as resolved while its squash is still in flight to IEW), applied at the moment the pending squash is released.
- **Why stock timing (commitToIEWDelay = 1) closes it.** IEW R+1 runs `checkSignalsAndUpdate` → `squash()` (IQ and LSQ) before `ldstQueue.updateVisibleState()` and `executeInsts()` (`iew_impl.hh:784-795, 1513-1524`). In the trace IEW logs `Squashing all instructions` at 3010000 = R+1. A deferred load is only re-scheduled once IEW has cleared its fenceDelay (`inst_queue_impl.hh:1225`), which never happens before the squash.
- **Alignment answer.** With delay D, the squash reaches IEW at R+D and the untaint is visible from IEW R+1. A load woken/issued in R executes at R+1 untainted, so it needs D ≥ 2. A load already deferred is re-issued at R+1 and executes at R+2, so it needs D ≥ 3. No alignment of B0's stall changes this, because before R B1's wrong path is always tainted.
- **Demo (30 runs, `s4_probe.py` from `bugwork/stt_a3s4/` unchanged; config `cfg_E3_stt_master_seexp.jsonc` = the E3 copy with only `config_script` → `/work/stt-master/configs/example/se_exp.py`, which equals `se.py` plus env-only timing knobs; `SIMSPECT_COMMIT_IEW_DELAY` = 2 and 3; stem `inst-000002`, `mispredict_not_taken`, B1 stall 0, B0 stall 114-128).** Results in `probe_d2/`, `probe_d3/` `probe_results.json`.
  - D=2: T executes only at stall 119 (T issued in R = 3009000, LSQ `Executing load` 3009500, squashed 3010000). It is `executed_no_packet`, never completed: T's address aliases the pc1 store (both `0x40(%rsp)`), so it forwards, and the forward is squashed before writeback. All other stalls `never_executed`.
  - D=3: T executes at stalls 118-128 (fresh issue at 118/119, deferred-then-reissued at R+1 for ≥ 120, as predicted). At stall 119 it is `store_forward` (completed 3009500, squash 3010500): a data-obtained leak by the check_ld gate. Stall 116 timed out (gem5 120 s guard).
  - Stock D=1: 0/600 executions per build (the previous agent's probe, `bugwork/stt_a3s4/probe_master`, `probe_old`).
- **What this means.** S4 should be folded into A4 as its "pending-squash release" trigger: same root cause (executed-but-unsquashed branch counts as resolved), same non-stock timing requirement. There is no separate stock-timing S4 bug, so no S4 model route is needed for a new bug. The paper's §6.4.1 delay is implemented correctly *while* the squash is pending. Note for the A4 write-up: the pending-squash path is another way to reach A4, and the window is the same one cycle per extra unit of commitToIEWDelay.
- **Side note (no bug):** the `(Lazy) Redirecting to PC 0x401c9d` line prints `nextPC.nextInstAddr()` after `advancePC` (`commit_impl.hh:1109-1129`), so the address is off; the real redirect (`commitInfo.pc = nextPC`) fetches `0x401c95` at 3011500. This is a print-only quirk.

## Areas reviewed (no new finding)

- **Load-side paths that might skip the taint delay (none found):**
  - The fenceDelay check happens in `executeInsts` before `executeLoad`/`initiateAcc` (`iew_impl.hh:1260`), so a tainted load gets no TLB lookup or page walk (`lsq_unit_impl.hh:827`).
  - Split/unaligned halves are issued from the same `read()` call.
  - Cache-blocked retries, partial-forward reschedules (`lsq_unit.hh:849`) and translation-delayed loads all re-enter through `executeInsts` or the deferred list, so they are re-checked. Taint only ever decreases (the `setPrevBrs*` flags are sticky and argProducers are fixed at insert).
  - Strictly-ordered and uncacheable loads execute at the head of the ROB.
  - Locked/LLSC loads are still `isLoad`, so they take the same gate.
  - x86 PREFETCH is a `ld … prefetch=True` microop (`insts/general_purpose/cache_and_memory_management.py:39-48`), so it is gated too.
  - Hardware prefetchers only see accesses that already happened, which have untainted addresses. That matches the paper's §6.4.2 p8 argument.
- **Decode, rename and the predictors (no data dependence):**
  - Decode squashes only for direct targets, which do not depend on data.
  - Rename has no value-dependent behaviour.
  - The RAS is pushed and popped at fetch, and repaired by `BPredUnit::squash(seq)` once commit sends the squash. A tainted RET's squash is pending because its `wrip` source comes from the speculative `ld`, which matches the RAS paragraph (§6.4.1 p7).
  - The BTB and direction predictor are updated only on a commit squash (untainted by then) or at retire.
  - The delayed-update path in fetch (`fetch_impl.hh:1021-1028`) is effectively dead code: taint only decreases, and commit has already held any tainted squash.
- **Per-cycle ordering:** a load dispatched in the same cycle cannot outrun taint at stock delays, because the ROB insert and `compute_taint` happen in commit before the next IEW execute.
- **Futuristic mode:** the definition `isUnsquashable ⟺ isPrevInstsCompleted` (`rob_impl.hh:476-487, 518`) has the same "executed counts as safe" structure, so A4/S4-style races presumably apply. It was not reviewed further because Futuristic is parked (Anna, 2026-11-07).
- **Class C:** with moreTransmitInsts=0, div and FP are not transmitters. gem5 FU latencies are fixed, so there is nothing to observe.
- **Note on known A3a/A3b:** the unused `hasImplicitFlow` does not contradict the paper. §6.4 p7 rejects tainting the instructions after a tainted branch (the "strawman DIFT approach") in favour of delaying resolution and predictor updates.

## Not reviewed

- Multi-thread paths (skipped; our SE runs are single-threaded).
- Ruby protocols (`--caches` only here).
- Classic-cache internals and MSHR/port contention timing.
- FS mode, interrupts and faults beyond what the Spectre model ignores. Non-branch squash sources are out of the Spectre contract by design.
- The x86 page-walker internals for untainted loads.
- InvisiSpec code paths, which `assert(0)` in this build.
- The SimSpect hooks beyond the resolve-stall note above (audited separately).

## Questions for Anna

- **Q1: does a branch that has executed but whose squash is still pending or draining count as "resolved" in the contract?** The code says yes, and that is the root cause of both A4 and S4. (Correction 2026-11-09, bug-investigate-s4trace: yes only once the squash is *draining*; while it is *pending*, `readyToCommit()` is false (`base_dyn_inst.hh:964-968`), so S4 reduces to A4 at the release cycle, see "S4 trace follow-up".) The paper delays a tainted branch's resolution (§6.4.1 p7).
  - Options: (a) keep the Alloy contract as is and count A4/S4 as implementation bugs; (b) also have the checker window treat a mispredicted branch as unresolved until its squash tick.
  - **Recommendation:** (a). Wrong-path instructions should never pass the visibility point, and S4 should be folded into the A4 bug write-up as its stock-timing variant once a gadget confirms it.
- **Q2: should S1 be shown with a gadget or through a vocabulary change?**
  - Options: (a) a one-off bugsynth gadget, xmm4 vs xmm3; (b) add xmm moves to Stage-2's `other` vocabulary (a concretization change, which needs your approval).
  - **Recommendation:** (a).
