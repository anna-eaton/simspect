# Source audit: SPT (gem5-spt @ 0d2be0f), 2026-11-08

Manual, read-only audit of `~/trippel/defense_src/spt_0d2be0f/` against the SimSpect SPT contract (`STAGE1_alloy/models/SPT_6_oneLP.als:368-396`, v2 draft `SPT_6_oneLP_v2.als:368-396`) and the paper (`~/Documents/quail/sources/papers/choudhary-2021-spt.pdf`). Two rounds; round 2 covered store addresses, Ruby, microcode/FP, rename/fetch and the InvisiSpec variant. Paths are relative to the SPT tree unless they say otherwise. Nothing was built or run; every claim is from reading code.

Main config (`runconfigs/fixed_20261030/SPT_6_oneLP_fence_fixed_latest.jsonc`, unit spt_fence): `--scheme=SpectreSafeFence --applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy --freeParam=3`, classic caches (no `--ruby`), shadow L1 off, `moreTransmitInsts=0`. So the transmitters are loads, stores and branches, and backward untaint is active.

## Summary

| ID | Class | Confidence | Claim | Known? |
|---|---|---|---|---|
| A1 | A | confirmed by reading; confirmed in simulation 2026-11-09 (hand test, not reached; see 'A1 gem5 check') | Backward untaint on `add/addi/sub/...` counts a flag (CC) source as an invertible operand. Declassifying an `inc`'s integer result untaints the older secret-derived CF/OF register; forward untaint then cleans `inc`'s CF output, so a speculative `jb` on `secret<k` resolves with no delay. | new |
| A2 | A | confirmed by reading | The backward MOV rule also fires on the conditional `mov` microop used by CMOVcc and CMPXCHG, untainting `regm` even when the condition was false and `regm` was never leaked. | new |
| A3 | A | confirmed by reading | An 8/16-bit write leaves the upper bytes of the new physical register marked public (rename clears all taint; only the written bytes are re-tainted), while their value is merged from the old, possibly secret register. `mov rax,[secret]; mov al,7; movzx ecx,ah` makes secret byte 1 public. | new |
| B1 | B | confirmed by reading | gem5 never declassifies a branch predicate at the VP (only load/store addresses). The paper (§6.3, §6.6) and the Alloy clause say it does. gem5 is stricter, so this hides no leak. | new |
| B2 | B (config) | confirmed by reading | In this tree `--scheme=SpectreSafeInvisibleSpec` is not InvisiSpec: loads are marked unsquashable and never delayed or made invisible. With `--configImpFlow=Ignore` (as in `runconfigs/run_config_SPT_6_SpectreInvisibleSpec.jsonc`), branch squashes aren't delayed either. That config is effectively an unprotected baseline. | new (the freeParam=0 part is known) |

Store addresses (round 2, item a): no defense bug found; details under "Areas reviewed".

## A1: backward untaint through a flags input (`inc` after `cmp secret`)

- **Code:** `src/cpu/o3/rob_impl.hh:855-873`:
  ```
  const char* opcodes = "add,addi,adc,adci,sub,subi,sbb,sbbi";
  if (strstr(opcodes, instName.c_str()) != nullptr) {
      if (!inst->renamedDestRegIdx(0)->isZeroReg() &&
          !inst->isNonCCDestTainted() &&
          inst->numTaintedSrcRegs() == 1)
          for (i...) if (inst->isArgsIdxTainted(i) ...) { argsTaintBcastMask.at(i) = true; ... break; }
  ```
  `numTaintedSrcRegs` (`base_dyn_inst_impl.hh:563-570`) counts every source register, CC registers included.
- **Why the flags register is a source (round 2: settled):** `INC_R` is `addi reg, reg, 1, flags=(OF, SF, ZF, AF, PF)` (`src/arch/x86/isa/insts/general_purpose/arithmetic/increment_and_decrement.py:41`). CF is not in `ext`, so the read predicate of `PredcfofBits` is true (`src/arch/x86/isa/operands.isa:155-158`). The ISA parser adds a predicated CC operand to `_srcRegIdx` exactly when that predicate holds in the constructor (`src/arch/isa_parser.py:866-869`: `if (read_predicate) {src_reg_constructor}`). So INC's sources are `reg` plus the CFOF register. The integer result (`regop.isa:507-508`, `psrc1 + op2`) does not depend on CFOF. CF is preserved into INC's CFOF output through `genFlags` (`regop.isa` FlagRegOp, the `ext` mask). A `jb` reads all five CC registers (`microops/seqop.isa:175`, `checkCondition(ccFlagBits | cfofBits | ...)`).
- **Mechanism:**
  1. `cmp r8,100`, with r8 secret, writes CFOF register C2 (tainted).
  2. `inc rcx`, with rcx public, reads rcx and C2. All its destinations are tainted at ROB insert (`rob_impl.hh:244-247`): rcx' and C3, where C3.CF = secret CF.
  3. `mov rdx,[rsi+rcx*8]` reaches the VP, and `untaintMemTransmit` untaints rcx' (`cpu.cc:2201`).
  4. Backward rule: `addi`, the non-CC destination is untainted, and exactly one source (C2) is tainted, so C2 is untainted. That is unsound.
  5. Forward rule (`rob_impl.hh:800`): INC's sources are all untainted now, so C3 is untainted.
  6. A `jb` behind an unresolved, mispredicted public branch has untainted arguments, so the Lazy delay (`commit_impl.hh:943-945`) doesn't hold it. Its squash or resolution reveals `secret < 100`.
- **Contradicts:** paper §6.6 (p. 612-613): backward untaint only for "invertible arithmetic … all but one of the inputs are untainted". Flags are not an arithmetic input of `inc`. Also the leakage function's `Branchxs.inreg`.
- **Litmus sketch:** `mov r8,[secret]` (committed) ; `cmp r8,100` ; `inc rcx` ; `mov rdx,[rsi+rcx*8]` ; `B: jne Lpub` (forced mispredict, stalled) ; `jb L2` (xmit). Check whether `jb` redirects before B resolves.
- **Can SimSpect generate or detect it?** Not generated: there's no flag-preserving add in the instruction tables and no flags state in the model. `check_br.py` would detect it. The slicer `STAGE3_gem5/triage/spt_cond_slice.py:244-260` does not model this flags path, so it would not explain such a hit away. That is correct.
- **Minor, same rule:** `adc`/`sbb` with only CFOF tainted untaints the whole CFOF register, releasing OF along with CF. The `strstr` substring match is sloppy, but I found no x86 microop name that matches by accident.

## A2: backward MOV rule applied to conditional moves

- **Code:** `rob_impl.hh:876-880`: `else if (instName == "mov") { if (!destTainted && inst->isArgsIdxTainted(1) ...) untaint src 1`.
- `Mov` is a `CondRegOp`: `DestReg = merge(SrcReg1, op2, dataSize)`, `else_code = 'DestReg = DestReg;'` (`src/arch/x86/isa/microops/regop.isa:751-753`). CMOVcc uses it with a condition (`insts/general_purpose/data_transfer/conditional_move.py:41-44`, `mov reg, reg, regm, flags=(CZF,)`). Round 2: CMPXCHG uses it too (`insts/general_purpose/semaphores.py:40-44`). By operand sort order (`operands.isa:92-98`), src 1 is `regm`.
- **Mechanism:** with the condition false, dest = old `reg`. The destination is tainted at insert because `regm` is tainted. Later the destination is declassified by a non-speculative transmitter, and the rule untaints `regm`, whose value was never exposed. A later speculative transmitter of `regm` then issues.
- **Contradicts:** paper §6.6 rule 1 ("register MOV r2 = r1") and Definition 1 (p. 611).
- **Litmus sketch:** `mov rbx,[secret]` ; set flags so the condition is false ; `cmovz rax, rbx` (not taken) ; `mov rcx,[tbl+rax]` (non-speculative; declassifies rax) ; `B` mispredicted ; `mov rdx,[tbl2+rbx*64]` (xmit). It should be delayed; per this code it issues.
- **Can SimSpect generate or detect it?** Not generated (no select/cmov in the vocabulary). `check_ld.py` would detect it. v2 keeps `regm` protected, so a hit would show. `spt_cond_slice.py` might misfile it as legitimate untaint if it parsed `cmov` as `mov`.

## A3: partial-width writes mark the merged upper bytes public

- **Code (round 2: settled):** rename clears the whole taint vector of every new destination register: `src/cpu/o3/rename_impl.hh:1180-1181`, `// [Rutvik, SPT] When an inst is renamed, its dest regs start out with a clean slate` / `cpu->setTaint(rename_result.first, false);`. ROB insert then re-taints only bytes `[offs, offs+dataSize)` (`base_dyn_inst_impl.hh:299-306, 341-354`; `regfile.hh:308-316`).
- For writes narrower than 4 bytes, x86 gem5 merges: the upper bytes of the new register are the old register's upper bytes (`regop.isa:507`, `limmop.isa:167`, `DestReg = merge(DestReg, ..., dataSize)`). Their taint is never copied, and the merge source is checked only on the overwritten bytes (`getSrcRegSizeAndOffs`, `base_dyn_inst_impl.hh:377-399`, same `dataSize`/offset).
- **Mechanism (needs no partial-untaint precondition):**
  1. `mov rax,[secret]`: P1 has all 8 bytes tainted.
  2. `mov al,7` (small `limm`): P2 byte 0 is tainted (the merge source's byte 0 is tainted); bytes 1-7 are public, but their values are secret bytes 1-7.
  3. `movzx ecx,ah` (`mov t1, t1, regm, dataSize=1` ; `zexti reg, t1, 7`, `insts/general_purpose/data_transfer/move.py:145-148`): AH reads P2 at offset 1 (`IntFoldBit`), which is public, so t1 and ecx are public.
  4. `B` mispredicted ; `mov rdx,[tbl+rcx*64]`: the address looks public, so the load issues and leaks secret byte 1.

  The same works with `mov al,[pub]` in step 2, or with 16-bit writes.
- **Contradicts:** paper §6.8 (byte-granular register taint) and Definition 1.
- **Can SimSpect generate or detect it?** Not generated (i64 IR emits no 8/16-bit writes; Alloy registers are whole values). `check_ld.py` would detect it.

## B1 (question): branch predicates are never declassified

`untaintMemTransmit` (`cpu.cc:2133-2207`, called from `lsq_unit_impl.hh:1207,1279`) handles only loads and stores. `untaintOtherTransmit` (`cpu.cc:2212-2222`) does nothing with `moreTransmitInsts=0`. When a branch reaches the VP its pending squash is released (`rob_impl.hh:1071-1075`), but its CC sources stay tainted. Paper §6.3 (p. 612: "the operands of transmitters/branches are untainted when the instruction becomes non-speculative") and §6.6 say otherwise, as does the Alloy clause (`nonspeculative_xmit_p` includes `Branchxs.inreg`). gem5 is stricter, so this cannot hide a leak.

## B2 (config): `SpectreSafeInvisibleSpec` in gem5-spt runs unprotected loads

- `cpu.cc:451-455`: `SpectreSafeInvisibleSpec` sets `loadInExec = true`.
- In `updateFenceDelays` (`lsq_unit_impl.hh:1142, 1234-1238`), every SPT taint check sits under `if (!cpu->loadInExec)`. The else branch is commented `// unsafe` and does `readyToExpose(true); isUnsquashable(true); fenceDelay(false);` for every load, so no load is delayed for a tainted address.
- `readyToExpose` is only ever set to true (the only writers are `lsq_unit_impl.hh:1233,1236`). So `initiateMemRead` never sets `Request::SPEC` (`base_dyn_inst.hh:1221-1223`), and `read()` always sends a plain `Packet::createRead` (`lsq_unit.hh:1016`). There is no invisible speculative read in this tree.
- With `--configImpFlow=Ignore`, `commit_impl.hh:917-918` handles every branch squash at once, so implicit channels are open too. The authors' `run_spt.py:38-44` only offers `SpectreSafeFence` / `FuturisticSafeFence`.
- **Affected configs:** `runconfigs/run_config_SPT_6_SpectreInvisibleSpec.jsonc:28` and the other unit-10 variant configs (`_FuturisticFence`, `_FuturisticInvisibleSpec`), which also use `Ignore` and omit `--freeParam`. With freeParam = 0 the untaint queue is size 0 (`rob_impl.hh:764`); that part is the known "freeParam=0 untaint-inert" bug. These configs are `to_run` / not run (`specs/defense_units.json` unit 10). Any campaign on them would show load and branch hits that are configuration, not SPT bugs. Futuristic schemes were not audited further.

## Areas reviewed / not reviewed

**Reviewed, no defense bug found:**

- **Store addresses (item a):**
  - Stores enter the SQ at dispatch; `updateFenceDelays` sets `fenceDelay = isAddrTainted()` before execute in the same IEW tick (`iew_impl.hh:1553-1560`, `lsq_unit_impl.hh:1246-1284`).
  - A delayed store is deferred before `executeStore` → `initiateAcc` → TLB translation (`iew_impl.hh:1305-1326`), so a tainted address reaches neither the TLB nor a page walk nor a split request.
  - `isAddrTainted` skips src 2 (data); x86 store operand order is Index, Base, Data, SegBase (`operands.isa:96-100,177`), so data is excluded correctly for `st`/`stupd`/`stfp`.
  - Store addresses are untainted only when the store reaches the VP (`lsq_unit_impl.hh:1268-1280`).
  - Forwarding only uses executed stores (known effective address). Speculative store bypass and its squash wait for STLPublic (`commit_impl.hh:944-945`, `lsq_unit.hh:630-660`), matching paper §6.7.
  - Takeaway for the 24 untriaged str hits: they need a real store checker. They are not evidence that this gate fails.
- **Ruby (item b):** grep shows no taint or shadow state under `src/mem/ruby`; all SPT state is in the O3 CPU. SimSpect runs classic caches (no `--ruby`), unlike the authors' `run_spt.py:56` (`--ruby --needsTSO=1`). For the fence scheme no load reaches memory before its gate, so Ruby vs classic should not change what leaks, only timing (not verified).
- **Microcode / FP (item c):**
  - String-op and locked-RMW microcode reach memory through `ld*`/`st*` microops, which hit the same gate. Microcode branches are control ops (`seqop.isa:177`).
  - FP/XMM registers are tracked at 8 bytes (`base_dyn_inst_impl.hh:299-306`, size 8 for non-int). Backward untaint doesn't fire on FP names (`movfp`, `addfp` don't match), which is conservative.
  - Gaps found: A1-A3 above, plus misc registers (next list).
- **Rename / fetch (item d):**
  - Fetch is redirected only by commit's squash (IEW only signals commit, `iew_impl.hh:485-509`), so a tainted branch's redirect waits for the delayed squash.
  - The branch predictor is updated only on that squash or at commit (`fetch_impl.hh:1040-1048`).
  - Rename clears taint on allocation (good; it is what makes A3 deterministic).
  - Commit sets the pending-squash flag before `markCompletedInsts` in the same tick (`commit_impl.hh:732-734`), so younger instructions never see a pending branch as resolved.
- **Also reviewed (round 1):** ROB taint and untaint, the VP computation, the Lazy delay, load gating, STL untaint and STLPublic, the store taint snapshot at commit.

**Noted, not written up (lower priority, end to end unverified):**

- Misc registers (MXCSR, FCW, the non-CC RFLAGS bits) have no taint file (`regfile.hh:135-149` → nullptr reads as untainted). `fldcw [secret]` → `fnstcw [buf]` → STL forward launders a secret to public (`save_and_restore_x87_control_word.py:40-61`). Class A, plausible.
- Shadow L1 (off in our runs) uses the last fragment's `pkt` for split loads/stores (`lsq_unit_impl.hh:175-260`) and ignores SE syscall memory writes.
- TrapPending skips the IEW squash while the branch is still marked resolved (unreachable in SE as far as I can tell).

**Not reviewed:** Futuristic schemes in depth, `ideal`/`untaintTier>0` modes, vector-register-class taint (x86 doesn't use it), the Eager scheme (it asserts out, `commit_impl.hh:920-922`), an exhaustive microop-name check against the `strstr` match, and SE syscall emulation paths generally.

## A5 gem5 check (2026-11-09, bug-investigate-a5): Fence has the same visibility-point ↔ squash race as STT A4

**Verdict: real implementation bug in gem5-spt (same class as STT A4), exposed only when the commit→IEW squash latency is ≥ 2 cycles. Stock gem5 timing (`commitToIEWDelay=1`) holds.** Under Anna's 2026-11-08 rule (a branch that has executed but not yet squashed counts as unresolved, URGENT_TODO line 43) this is an implementation bug, not a checker artifact. Our generated tests hit it (slow-comm campaign 2026-06-02; reproduced today).

**Mechanism (gem5-spt source, `~/trippel/defense_src/spt_0d2be0f/src/cpu/o3/`):**

- Commit tick: `commit()` handles IEW's mispredict squash (`commit_impl.hh:946-964`, Lazy scheme, untainted branch → `handleSquashSignalFromIEW`); the ROB marks younger insts squashed `squashWidth` per cycle, youngest first (`rob_impl.hh:415-445`). Then `markCompletedInsts()` (`commit_impl.hh:734`) sets the mispredicted branch `CanCommit` (`commit_impl.hh:1692`) and calls `rob->updateVisibleState()` (`:1699`).
- `updateVisibleState` treats a control inst as resolved when `readyToCommit() && no fault` (`rob_impl.hh:531-535`), with no check for a misprediction or a squash in flight, and marks every younger not-yet-squashed inst `isUnsquashable` = reached the VP (`rob_impl.hh:557-569`).
- IEW tick: `checkSignalsAndUpdate` reads commit's squash through the `commitToIEWDelay` time buffer (`iew_impl.hh:788`), then `ldstQueue.updateVisibleState()` (`iew_impl.hh:1557`) runs `updateFenceDelays`: an unsquashable load is untainted (`untaintMemTransmit`, `lsq_unit_impl.hh:1207`) and un-fenced (`fenceDelay(false)`, `:1211`), then `executeInsts()` issues it.
- With `commitToIEWDelay=1` the squash reaches IEW in the same tick the load would be released, and is processed first → load never executes. With ≥ 2 the wrong-path transmitter is released and sends its cache packet one cycle after resolution, one cycle before the LSQ squash.

**Experiment** (cafe2 `/tests/simspect_alloy_20261108/bugwork/a5/`, `run.sh`, `summary.txt`, `res_*.json`): 24 stems sampled (seed 5) from the 341 genuine race stems of `results/experiments/spt_slowcomm_fence__20260602_121858` (not_taken, `postmispred_producer ∩ stt_vp_squash_race` minus rf_clobber / nonspec / store co-transmit), old `SPT_6_oneLP` testset. Harness: current `check_ld.py` (`/tests/simspect_fixed_20261030`), the slow-comm campaign's run config (gem5-spt, DerivO3CPU, branch_ann on, `O3PipeView,LSQUnit`, flags `--applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy --scheme=SpectreSafeFence`, fnc stall 150). **Added explicitly:** timing knobs through a scratch copy of `se.py` (`bugwork/a5/se_knobs.py`, env `A5_*`; the gem5 tree is untouched). Leak = in window and data obtained (check_ld `_xmit_cache_fate` gate); every leak below is `reached_cache` (a real packet), none `store_forward`.

| Variant | Timing | Leaks / 24 |
|---|---|---|
| V0 slow-comm verbatim (`se_slowcomm.py`) | iewToCommit 30, commitToIEW 4, squashWidth 1, comSize 40 | 24 |
| V1 stock `se.py` | commitToIEW 1 | 0 (all `never_executed`) |
| V2 | commitToIEW 2 only | 3 |
| V3 | commitToIEW 3 only | 14 (1 gem5 timeout) |
| V4 | commitToIEW 4 only | 15 (1 timeout) |
| V5 slow-comm, fnc stall 0 | as V0 | 24 reach cache; 15 inside check_ld's window |
| V6 current campaign config (`SPT_6_oneLP_fence_fixed_latest`: `--freeParam=3`, fnc 0) + commitToIEW 4 | | 15 reach cache; 11 in window (1 timeout) |
| V7 slow-comm with commitToIEW 1 | iewToCommit 30, squashWidth 1, comSize 40 | 0 |
| V8 current campaign config verbatim | stock | 0 |

- **Driver = `commitToIEWDelay` alone** (V7 vs V0: all other slow-comm knobs together give 0). `squashWidth=1` and `iewToCommitDelay=30` widen it once the delay is ≥ 2 (V4 15 → V0 24) but do not cause it. Same as STT A4.
- **Not the fnc-commit-stall hook** (V5: 24/24 still send a packet with the stall off; the stall only changes how many fall inside check_ld's lc/fnc window). Not `freeParam` (V6). The BTB-force hook only supplies the mispredict.
- **Trace example, `inst-038517` (V2, commitToIEWDelay=2; 500 ticks/cycle):** mispredicted branch 0x401c65 sn 578 resolves at 2950500, transmitter load 0x401c6c sends its cache packet at 2951000, LSQ squash at 2951500. At stock (V1) the same load is `never_executed`. Also `inst-040085` (resolve 2949000 / packet 2949500 / squash 2950000) and `inst-064173` (2949500 / 2950000 / 2950500).
- **Known non-bugs ruled out:** (1) zero-init prologue untaint: shadow L1 is off, taint is speculation-independent (`rob_impl.hh:240`), and at stock the same loads stay fenced (V1 0/24 never execute), so their address is tainted; (2) STLF over-approximation: every leak is `reached_cache`, none `store_forward`; (3) check_ld FP: real packets; (4) model over-approximation: these stems take their address from a post-mispredict speculative load (the `postmispred_producer` bucket, model-bug buckets removed).
- **Correction to the round-1 note above** ("Commit sets the pending-squash flag before `markCompletedInsts` …, so younger instructions never see a pending branch as resolved"): that holds only for a Lazy-*pending* (tainted-argument) branch. An untainted mispredicted branch is not pending; it is marked resolved in the same tick its squash starts, which is the A5 race.
- **Scope:** reachable from the default SPT_6_oneLP corpus (the old slow-comm campaign has 341 not_taken genuine race stems of this shape; 983 over both modes per claudelog 2026-06-02 23:30); needs a raised `commitToIEWDelay` (not wired into `pipeline.py`; only via `se_slowcomm.py` or a scratch config). A one-line fix would be to stop treating a mispredicted control inst as resolved (`rob_impl.hh:533`) until its squash finishes; not tested (no gem5 edits).

## Questions for Anna

1. **B1: should the Alloy clause keep declassifying branch predicates?** (a) Keep it, following the paper; gem5 is stricter, which is safe. (b) Drop `Branchxs.inreg` from the declassification term to match gem5. (c) Record it as a paper/implementation gap only. **Recommendation:** (c). It cannot hide a leak.
2. **B2: what should happen to the unit-10 SPT variant configs?** (a) Drop `SpectreSafeInvisibleSpec` / `FuturisticSafeInvisibleSpec` for gem5-spt (they aren't SPT schemes in this tree). (b) Keep them as labelled "unprotected-load" baselines. (c) Fix them to `Lazy` + `--freeParam=3` and run only `FuturisticSafeFence`, the scheme the authors support. **Recommendation:** (a) + (c): it matches `run_spt.py:38-44` and stops non-bugs from entering the results.
3. **A1-A3 are unreachable with today's vocabulary and Alloy shapes. Do we want them testable?** (a) Add `inc`/`dec`, `cmovcc` and 8-bit ops to the instruction tables. (b) Hand-write the three litmus programs as a directed check on `/work/gem5-spt` with the spt_fence flags. (c) Report them as source-audit findings only. **Recommendation:** (b) first. It is cheap and settles the end-to-end question before any vocabulary or model work.

## A2 gem5 check (2026-11-09, bug-investigate-spta2): the false-cmov backward untaint is real, but our pipeline does not reach it

**Verdict: real gem5-spt bug, confirmed in simulation with a hand-edited test; not reached by generated tests.** A false `cmovne` (the `cmov_rr` form) whose output is declassified by a non-speculative load untaints the cmov's never-moved source, and a wrong-path load using that source then issues under SpectreSafeFence while the mispredicted branch is still held. Three things stop the pipeline from finding it today: the pre-v2 model never makes the shape a violation, the cmov must still be in the ROB when the declassifying load reaches its VP, and `check_ld`'s window lower bound (`lc_retire < signal`) does not count a wrong-path load that executes before the last committed instruction retires.

**Code path (build `/work/gem5-spt` @ 0d2be0f).** `CMOVNZ_R_R` is two `mov` microops, `mov reg, reg, reg, flags=(CZF,)` then `mov reg, reg, regm, flags=(nCZF,)` (same file as `conditional_move.py:41-44`). The generated `MovFlags` constructor orders sources `src1, src2, dest, ZAPS, CFOF, DF, ECF, EZF` (`build/X86_MESI_Two_Level/arch/x86/generated/decoder-ns.cc.inc:5538-5566`), so src index 1 is `regm` and the microop name is `"mov"`. The backward rule `rob_impl.hh:876-880` untaints src 1 once the destination is untainted, with no check of the condition.

**Experiment** (cafe2 `/tests/simspect_alloy_20261108/bugwork/spta2/`, code = Mac snapshot `code_20261109`, config = `runconfigs/fixed_20261030/SPT_6_oneLP_fence_fixed_latest.jsonc` with only the testset/results paths, the instruction table and `branch_modes: [mispredict_not_taken]` changed). Template: SPT v2 (n10_pinb) `inst-000001`, fv2_vocab concretization: pc0 `L: mov (%r15,%r11),%r11` (load, value tainted), pc1 mispredicted branch (held 5000 cycles), pc4 transmitter `X: mov (%r15,%r11),%r11`. `mk_hand.py` inserts between pc0 and pc1 an op `O(in0=%r10 public, in1=%r11)` → `%r8`, then `D: mov (%r15,%r8),%rdx` carrying the `last_committed` label. Variants: T = O is `cmov_rr` exactly as parsexml emits it (`movq %r10,%r8; cmpq %r10,%r10; cmovneq %r11,%r8`); C1 = same cmov but D reads `%r10` (no declassification of the cmov output); C2 = O is `leaq` (no backward rule); C3 = O is `movq %r11,%r8` (the legitimate backward mov); C0 = unchanged. `ts_hand_al` adds `.p2align 6` before pc0 so that L..D share one I-cache line.

| variant | X executes while the branch is held? (point 0, aligned, `Executing load PC (0x401cad…)`) | check_ld sweep hits, aligned | check_ld sweep hits, unaligned |
|---|---|---|---|
| T cmov_rr, D declassifies the cmov output | **yes, tick 3007500** (sn 576), same tick as D (sn 559); branch `0x401c9d` `resolve_hold … fire=5506500` | 0/243 | 0/243 |
| C1 cmov_rr, no declassification | no (X never executes before the squash) | 0/243 | 0/243 |
| C2 leaq | no | 0/243 | 0/243 |
| C3 true mov | yes, tick 3007000 (legitimate) | 0/243 | 243/243 |
| C0 unchanged | no | 0/243 | 0/243 |

So T vs C1 isolates the declassification of the false cmov's output, and T vs C2 isolates the `mov` microop name. X's address `%r11` holds the load L's value, which the cmov never moved.

**Why the generated pipeline misses it.**

1. **Model.** The pre-v2 SPT clause declassifies backward through every op edge, `- (i.operands & nonspeculative_xmit_p[p]).*(~(op_edges_p[p]))` (`STAGE1_alloy/models/SPT_6_oneLP.als:349`), so it removes both ALU inputs from protection when the output leaks. That is A2's over-untaint, so the model never makes this test a violation. Census of 2,000 pre-v2 `testsets_latest/SPT_6_oneLP` XMLs concretized with fv2_vocab: 111 tests per mode got `cmov_rr`, 1 had a load-derived `in1`, and 0 had the cmov output feeding a pre-branch address (`find_a2.py`, `census_fv2_pre_{nt,t}.txt`). v2/v3 declassify only along rf (`proposed/SPT_6_oneLP_v3.als:393`), so they keep `in1` protected and could generate the shape. This is not verified: the 100-instance v2 sample had no `cmov_rr`, and no Alloy query was run.
2. **ROB residency.** The backward rule only walks instructions still in the ROB (`propagateUntaint`, `rob_impl.hh:774`). In the unaligned T, D was in the next I-cache line, was fetched at tick 2945000 (L at 2887500), after the cmov had already committed (2901000), so nothing was untainted. Aligned, all of them are in flight together.
3. **Checker window.** X executes before D, the last committed instruction, retires (3009500), so `check_ld`'s `lc_retire < signal` bound rejects it at every sweep point. The same happens to the legitimate C3 leak once aligned. This is a window-definition question, not an SPT question (URGENT_TODO DECIDE).

Not done: gem5-spt's own `--trackInstsFile` taint tracer crashes this build (`track_T/`, a Python backtrace from gem5), so the evidence is the differential above rather than a "marked for untainting via backward propagation" line. Scripts with usage headers: `find_a2.py`, `mk_hand.py`, `run_point.py`; traces kept under `pt0al_*/` and `pt0_*/`.

## A3 gem5 check (2026-11-09, bug-investigate-spta3): the 8-bit merge leaves the upper bytes public; real, not reached

**Verdict: real gem5-spt bug, confirmed in simulation with a hand-edited test; not reached by generated tests (our IR emits no 8/16-bit register writes).** After `movq %r11,%rax` (rax fully tainted, from a load), `movb $7,%al` gives the new physical register taint only on byte 0, so `movzbl %ah,%ecx` reads byte 1 (the old secret byte) as public, and a wrong-path load on `%rcx` issues under SpectreSafeFence while the mispredicted branch is held. Unlike A2, `check_ld` scores it at every sweep point (243/243), so no checker change is needed.

**Code path (build `/work/gem5-spt`, read 2026-11-09).** Rename clears the whole taint vector of each new destination: `src/cpu/o3/rename_impl.hh:1180-1181`. ROB insert taints the destination when any source is tainted, `rob_impl.hh:244-247` (`isArgsTainted` → `setDestTaint(true)`), but `setDestTaint` writes only `[offs, offs+dataSize)` (`base_dyn_inst_impl.hh:341-354` via `getDestRegSizeAndOffs` `:297-306`, `regfile.hh:308-316`). `MOV_R_I` is `limm reg, imm` (`arch/x86/isa/insts/general_purpose/data_transfer/move.py:76-78`), whose code is `DestReg = merge(DestReg, imm, dataSize)` (`arch/x86/isa/microops/limmop.isa:167`), so bytes 1-7 of the new register carry the old (secret) value but stay untainted from rename. `MOVZX_B_R_R` reads AH with `dataSize=1` at offset 1 (`move.py:145-148`; `getSrcRegSizeAndOffs` `base_dyn_inst_impl.hh:377-399`; `isArgsIdxTainted` `:416-428` checks only that byte).

**Experiment** (cafe2 `/tests/simspect_alloy_20261108/bugwork/spta3/`; code = `code_20261109`; config = spta2's `cfg_hand_al_T_cmov.json`, i.e. `runconfigs/fixed_20261030/SPT_6_oneLP_fence_fixed_latest.jsonc` with only the testset/results paths, fv2_vocab table, `branch_modes: [mispredict_not_taken]` changed, plus `keep_tmp: false`). Template: the same SPT v2 (n10_pinb) `inst-000001` fv2 concretization as A2 (pc0 `L: mov (%r15,%r11),%r11`, last_committed; pc1 mispredicted branch, held 5000 cycles; pc4 transmitter). `mk_hand.py` adds `.p2align 6` before pc0, inserts one asm block after L, and changes X to `movq (%r15,%rcx),%r11`. Variants: T8 = `movq %r11,%rax; movb $7,%al; movzbl %ah,%ecx`; C1 = `movq %r11,%rax; movzbl %ah,%ecx` (no partial write); C2 = `movq %r11,%rax; movl $0x700,%eax; movzbl %ah,%ecx` (32-bit write); C0 = unchanged.

| variant | X executes while the branch is held? (point 0, hold 5000) | check_ld sweep hits |
|---|---|---|
| T8 8-bit merge, read AH | **yes**: `3009000: Executing load PC (0x401ca7…) [sn:575]`, packet sent; branch `0x401c97` `resolve_hold … fire=5506500`; full.json `in_window=True, data_obtained=True, cache_fate=reached_cache`, lc_retire 3007500 < signal 3009000 < fnc_retire 5515000 | **243/243** |
| C1 no partial write | no (`xmit_cmp=0`, never executes before the squash) | 0/243 |
| C2 32-bit write | not traced | 0/243 |
| C0 unchanged | not traced (A2 showed it does not execute) | 0/243 |

T8 vs C1 isolates the 8-bit write: the same AH byte holds the same secret byte in both, and only the merge write makes it look public. C2 is not a "public" control: `limm` with dataSize 4 still reads `DestReg` as a source, so bytes 0-3 are re-tainted (over-taint, which hides nothing). I did not test the 16-bit form: after `movw $imm,%ax`, bytes 2-7 are public but x86 has no sub-register at offset 2, and any wider read also covers the tainted bytes 0-1, so the 8-bit write + AH read is the observable instance. Traces kept: `pt0_T8/`, `pt0_C1/` (staged `.s`/`.ann.json` in `stage_*`); scripts `mk_hand.py`, `run_point.py`, `run_all.sh`; logs `log_gem5_*.txt`.

**Why the generated pipeline misses it, and what it would take.**

1. **Vocabulary.** parsexml emits only `i64` operations; 0 of 93,041 `STT_6_fv2` (and 0 of 93,041 `STT_6_fv2fp`) mispredict_not_taken `.s` files contain `movb`/`movw`, `%al`-style or `%ah`-style registers or `setcc` (grep on cafe2 `testsets_twostage/*/mispredict_not_taken/asm`). VOCAB_TABLES G1 (narrow loads/stores) does not cover this: `movzbq` from memory writes the whole register. A3 needs two new register ops, a merging 8-bit write (`movb $imm, ${0:b}` with constraint `"=Q,0"`, or a register-source `movb`) and a high-byte read (`movzbl ${1:h}, ${0:k}` with `"=Q,Q"`). Probe `probe_hbyte.ll` compiles to `movb $7,%al` / `movzbl %ah,%eax` with cafe2 clang.
2. **Register class.** AH/BH/CH/DH exist only for rax/rbx/rcx/rdx and cannot be encoded in an instruction with a REX prefix, so the merged register must be one of those and the `movzbl` destination must also be a non-REX register (no r8-r15, no sil/dil). parsexml pins registers physically (`={r11}`), so its register naming would need to steer the slots on this chain to rax/rcx/rdx (rbx is not in the caller-saved pool; rsi is an infra register). Today's random naming picks r8-r11 often (this template's chain register is r11).
3. **Model.** No model change is needed: the SPT model propagates protection forward through `other` ops, so a merge-write + high-byte-read spliced onto the producer→transmitter rf edge (VOCAB_TABLES approach (c), "Fanout v2 proposal" row SPT A3) keeps every model violation a violation. Through Alloy alone it would need two `other` ops on the transmitter's address path, which the capped enumeration rarely produces (see the OTB caveat in CLAUDE.md).
4. **Checker.** None: T8 scores 243/243 because X waits for L's data, so it executes after `lc_retire`.

The parsexml/vocabulary change is approval-gated (VOCAB_TABLES V4); this hand test does not count as found by us.

## A1 gem5 check (2026-11-09, bug-investigate-spta1): declassifying an `inc` result untaints the secret compare's flags; real, not reached

**Verdict: real gem5-spt bug, confirmed in simulation with a hand-edited test; not reached by generated tests (no generated jcc ever reads flags older than its own `cmpq`).** After `cmpq $100,%r11` (r11 = a loaded, tainted value) and `incq %r10` (r10 public), a non-speculative load on `8*%r10` untaints the compare's CF/OF register through the backward `addi` rule. A wrong-path `jb` that reads that CF then broadcasts its mispredict squash at tick 3009000, while the older mispredicted branch is held until 5508500. Without the declassifying load, the same `jb` is "made pending" by the Lazy delay and never redirects. check_br scores the test 243/243 (controls 0/243).

**Code path (build `/work/gem5-spt`, read 2026-11-09).** `INC_R` is `addi reg, reg, 1, flags=(OF, SF, ZF, AF, PF)` (`src/arch/x86/isa/insts/general_purpose/arithmetic/increment_and_decrement.py:41`). The generated `AddFlagsImm` constructor (`build/X86_MESI_Two_Level/arch/x86/generated/decoder-ns.cc.inc:2479`) adds `CCREG_CFOF` as a source when exactly one of CF/OF is set in `ext` (`:2508-2510`), which is the INC case, and writes CFOF as a destination (`:2513`). The trace names the microop `INC_R : addi r10, r10, 0x1`. Backward untaint (`src/cpu/o3/rob_impl.hh:854-873`) matches `addi` in the opcode string, sees the non-CC destination untainted and exactly one tainted source (CFOF), and untaints it. Forward untaint (`rob_impl.hh:799-800`) then cleans INC's (and the later `dec`'s) CC outputs, so the `jb`'s sources are all untainted and the Lazy check (`commit_impl.hh:941-945`, `isArgsTainted()`) does not hold its squash.

**Experiment** (cafe2 `/tests/simspect_alloy_20261108/bugwork/spta1/`; code = `code_20261109`; config = spta3's `cfg_T8.json`, i.e. `runconfigs/fixed_20261030/SPT_6_oneLP_fence_fixed_latest.jsonc` with only the testset/results paths, fv2_vocab table, `branch_modes: [mispredict_not_taken]` and `keep_tmp: false` changed; TMPDIR inside bugwork). Template: the same SPT v2 (n10_pinb) `inst-000001` fv2 concretization as A2/A3 (pc0 `L: mov (%r15,%r11),%r11`, last_committed; pc1 mispredicted branch held 5000 cycles). `mk_hand.py` makes four edits: (1) `.p2align 6` before pc0; (2) one asm block after L (the variants below); (3) pc1's condition becomes `movq $1,%rsi ; decq %rsi ; je` instead of `cmpq $1,%rsi ; jae`, because `dec` preserves CF while every br_cmp `cmpq` overwrites it (same architectural direction: taken, forced predict not-taken); (4) pc2 (a direct jmp in the template) becomes `jb end ; jmp pc3` and is the transmitter (ann `xmit` pc2 kind `br_x`, annotated `mispredict_not_taken`, so it is forced predict not-taken; CF=1 in every variant, so `jb` is architecturally taken and mispredicted). check_br is chosen by `xmit.kind`.

| variant | asm block after L | jb (sn 566) squash while pc1 (sn 563) is held? (point 0, `stage_*` → `pt0_*`) | check_br sweep hits |
|---|---|---|---|
| T | `cmpq $100,%r11 ; incq %r10 ; movq (%r15,%r10,8),%rdx` | **yes**: `3009000: Squashing due to branch mispred PC:0x401c9b [sn:566]`; pc1 `0x401c99` `resolve_hold … fire=5508500`, its squash at 5509000; full.json `issued_in_window=True`, lc_retire 3007500 < redirect 3009000 < fnc_retire 5516500, all validity criteria True | **243/243** |
| C1 | `cmpq $100,%r11 ; incq %r10 ; movq (%r15),%rdx` (inc's result not declassified) | no: `3009000: (Lazy) A branch mispredicInst [sn:566] PC (0x401c9a=>…) is made pending`, no redirect before pc1 | 0/243 |
| C2 | `cmpq $100,%r11 ; leaq 1(%r10),%r10 ; movq (%r15,%r10,8),%rdx` (declassified op has no flags source) | no (`xmit_redirect=0`) | 0/243 |
| C3 | `cmpq $100,%r10 ; incq %r10 ; movq (%r15,%r10,8),%rdx` (flags from a public compare; positive control) | yes, legitimately (redirect 3008000) | 243/243 |

T vs C1 isolates the declassification of inc's output: the secret compare, the `inc`, the `jb` and its CF value are identical, and only D's address differs. T vs C2 isolates INC's flags source (same declassifying load, no CFOF input on the declassified op). C3 shows the harness observes a public-flag `jb` redirect under the same hold. Timing in T: D (`0x401c8b`, sn 558) executes at 3008000; the INC (sn 557) retires at 3008500, so it is still in the ROB when D untaints r10; the `jb` squashes at 3009000; D retires at 3010500. Traces kept: `pt0_T/`, `pt0_C1/` (only `full.json` for `pt0_C2/`, `pt0_C3/`; staged inputs in `stage_*`); scripts `mk_hand.py`, `mk_pt0.py`, `run_point.py`, `run_all.sh`, `summ.py`, `census_a1.py`; logs `log_gem5_*.txt`, `summary.txt`.

**Why the generated pipeline misses it, and what it would take.**

1. **Flags plumbing in Stage 2.** With `br_cmp`, every annotated jcc is emitted in one asm-goto block right after its own `cmpq $1,%c`, so it reads only that compare's flags. Census (`census_a1.py`) over cafe2 `testsets_twostage/STT_6_fv2/<mode>/asm`: 178,328 (not_taken) and 94,974 (taken) jccs in 93,041 tests per mode; **0** are not immediately preceded by a `cmpq`, and **0** have an `inc`/`dec` as their last flag writer (8,793 and 690 tests contain an `inc`, always in its own block). There is no SPT fv2 testset yet.
2. **What A1 needs (beyond the queue note "an `inc` between cmp and jcc").** The `inc` and the declassifying load must be older than the mispredicted branch B (under Fence a load declassifies only at its visibility point, i.e. with no older unresolved branch), and the `jb` must be younger than B. So the transmitter's compare must be emitted before B, and **B's own condition must not overwrite CF**. Today every B is `cmpq ; jcc`, which does. My test used `decq ; je` for B; `jrcxz`/`loop` would also work. So Stage 2 would need: (a) the transmitter branch's `cmpq` hoisted to a point before the declassifying load and B (an emission reordering across Alloy instructions); (b) an `inc` on a public register whose output feeds a committed load's address, placed between that `cmpq` and the load; (c) a flags-preserving form for the intervening unresolved branches. All three are parsexml changes (approval-gated; VOCAB_TABLES V4 note on `br_cmp` reordering). No model change is needed for the shape: the transmitter branch on the loaded value and a committed load on a public chain exist in SPT_6 today, and the model has no flags state, so the leak comes from gem5's CFOF source, not from a model edge.
3. **Checker lower bound.** With the last-committed label on L (as in the template), check_br scores 243/243. A generated test would put last_committed on the declassifying load D (it is committed in the model), and D retires at 3010500, after the `jb`'s squash at 3009000, so check_br's `after_lc` (`xmit_signal > lc_retire`) would reject it, the same lower-bound issue as A2 (URGENT_TODO DECIDE on the window lower bound).
4. **Triage.** `STAGE3_gem5/triage/spt_cond_slice.py:244-260` does not model the flags path (see A1 above), so a generated hit would not be explained away.

This hand test does not count as found by us.
