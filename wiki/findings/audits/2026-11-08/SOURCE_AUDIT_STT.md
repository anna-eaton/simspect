# Source audit: upstream STT gem5 (cwfletcher/stt @ e3283b9), 2026-11-08 trial run (round 2)

This is a read-only manual audit of `~/Documents/stanford/trippel/defense_src/stt_e3283b9/src` (paths below are relative to `src/`). It checks the code against the inferred STT contract (`STT_6.als:325-332`, `specs/leakage/stt.json`) and against the paper (`~/Documents/quail/sources/papers/yu-2019-stt.pdf`, MICRO'19). Our config for `/work/stt` is X86 O3, SE mode, classic `--caches`, STT=1, threatModel=Spectre, implicitChannel=1, needsTSO=0, moreTransmitInsts=0 (`gem5-hooks/stt/se_exp.py:326-333`). Nothing was run in gem5; every finding comes from reading the code. Stock timing below means the O3CPU.py defaults: renameToROBDelay=1, renameToIEWDelay=2, issueToExecuteDelay=1, iewToCommitDelay=1, commitToIEWDelay=1.

## Summary (new findings)

| ID | Class | Confidence | Claim | Known? |
|---|---|---|---|---|
| S1 | A | confirmed by reading | Taint is never propagated through FP register index 16 (= the low half of XMM4). The "zero register" skip ignores register class, and no other register class collides with it. | new |
| S4 | A | confirmed by reading (schedule); reachability depends on dispatch timing | At stock timing, a mispredicted branch with a tainted predicate opens a one-cycle window. When an older branch resolves, its wrong path is untainted one commit cycle before its delayed squash fires, so a wrong-path load issued in that cycle executes and reaches the cache. | new; same family as known A4, but A4 does not leak at stock timing |

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

- **Q1: does a branch that has executed but whose squash is still pending or draining count as "resolved" in the contract?** The code says yes, and that is the root cause of both A4 and S4. The paper delays a tainted branch's resolution (§6.4.1 p7).
  - Options: (a) keep the Alloy contract as is and count A4/S4 as implementation bugs; (b) also have the checker window treat a mispredicted branch as unresolved until its squash tick.
  - **Recommendation:** (a). Wrong-path instructions should never pass the visibility point, and S4 should be folded into the A4 bug write-up as its stock-timing variant once a gadget confirms it.
- **Q2: should S1 be shown with a gadget or through a vocabulary change?**
  - Options: (a) a one-off bugsynth gadget, xmm4 vs xmm3; (b) add xmm moves to Stage-2's `other` vocabulary (a concretization change, which needs your approval).
  - **Recommendation:** (a).
