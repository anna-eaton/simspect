# Source audit: SPT (gem5-spt @ 0d2be0f), 2026-11-08

Manual, read-only audit of `~/Documents/stanford/trippel/defense_src/spt_0d2be0f/` against the SimSpect SPT contract (`STAGE1_alloy/models/SPT_6_oneLP.als:368-396`, v2 draft `SPT_6_oneLP_v2.als:368-396`) and the paper (`~/Documents/quail/sources/papers/choudhary-2021-spt.pdf`). Two rounds; round 2 covered store addresses, Ruby, microcode/FP, rename/fetch and the InvisiSpec variant. Paths are relative to the SPT tree unless they say otherwise. Nothing was built or run; every claim is from reading code.

Main config (`runconfigs/fixed_20261030/SPT_6_oneLP_fence_fixed_latest.jsonc`, unit spt_fence): `--scheme=SpectreSafeFence --applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy --freeParam=3`, classic caches (no `--ruby`), shadow L1 off, `moreTransmitInsts=0`. So the transmitters are loads, stores and branches, and backward untaint is active.

## Summary

| ID | Class | Confidence | Claim | Known? |
|---|---|---|---|---|
| A1 | A | confirmed by reading | Backward untaint on `add/addi/sub/...` counts a flag (CC) source as an invertible operand. Declassifying an `inc`'s integer result untaints the older secret-derived CF/OF register; forward untaint then cleans `inc`'s CF output, so a speculative `jb` on `secret<k` resolves with no delay. | new |
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

## Questions for Anna

1. **B1: should the Alloy clause keep declassifying branch predicates?** (a) Keep it, following the paper; gem5 is stricter, which is safe. (b) Drop `Branchxs.inreg` from the declassification term to match gem5. (c) Record it as a paper/implementation gap only. **Recommendation:** (c). It cannot hide a leak.
2. **B2: what should happen to the unit-10 SPT variant configs?** (a) Drop `SpectreSafeInvisibleSpec` / `FuturisticSafeInvisibleSpec` for gem5-spt (they aren't SPT schemes in this tree). (b) Keep them as labelled "unprotected-load" baselines. (c) Fix them to `Lazy` + `--freeParam=3` and run only `FuturisticSafeFence`, the scheme the authors support. **Recommendation:** (a) + (c): it matches `run_spt.py:38-44` and stops non-bugs from entering the results.
3. **A1-A3 are unreachable with today's vocabulary and Alloy shapes. Do we want them testable?** (a) Add `inc`/`dec`, `cmovcc` and 8-bit ops to the instruction tables. (b) Hand-write the three litmus programs as a directed check on `/work/gem5-spt` with the spt_fence flags. (c) Report them as source-audit findings only. **Recommendation:** (b) first. It is cheap and settles the end-to-end question before any vocabulary or model work.
