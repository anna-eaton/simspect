# STT drops taint through xmm4 (FP register index 16): real gem5 defense bug

*2026-11-08, fpr-fanout session. Source finding: `wiki/findings/audits/2026-11-08/SOURCE_AUDIT_STT.md` S1. Found by SimSpect's own pipeline (Stage-2 FPR routing, `specs/fanout/fpr.json`).*

## Claim

Upstream STT (`/work/stt`, cwfletcher/stt @ e3283b9) loses taint whenever a value is read from the low half of xmm4. When a speculative load's value is copied through xmm4 and back, the dependent transmitter load executes inside the speculative window and reaches the cache. On 100 STT_6 load→load leak instances that STT holds in their GPR form, copying the access load's value through xmm4 makes **98/100 leak**. The same copy through xmm3 leaks **0/100**, and the GPR baseline leaks **0/100**. AMuLeT's STT build carries the same skip in its source.

## Evidence

| variant (same 100 stems, `mispredict_not_taken`) | `/work/stt` hits (check_ld data-obtained gate) | in-window fates (stems) | `gem5-recon-modded` hits |
|---|---|---|---|
| GPR baseline (FPR option off) | 0/100 | none in window | 10/100 |
| route via xmm3 (control, FP index 14) | 0/100 | none in window | 8/100 |
| route via xmm4 (FP index 16) | **98/100** | reached_cache 90, store_forward 8, executed_no_packet 2 (not leaks) | 8/100 (all also hit in the GPR baseline) |

- Every run used the canonical STT fixed-harness config `runconfigs/fixed_20261030/STT_6_stt_fixed_latest.jsonc` (and `STT_6_reconmodded_fixed_latest.jsonc` for recon), verbatim except `paths.testset_dir` and `paths.results_name` (diff logged in `run.log`). That means the same binary, scheme 2, branch force, resolve stalls, sweep points 0/500/2500, and fnc stall 0. Every grid point had `status=ok` with the validity criteria (resolved_correct, window_opened, stall_applied, force_applied) all true or not applicable.
- The stems are a seeded sample (`random.Random(20261108)`) of the 1358 of 1364 held `ld` tests in `results/STT_6_stt_fixed_latest__20261108_012818` whose transmitter address is the outreg of a speculative load (Alloy producer after the commit boundary). Same stems, so the 2% `sample_keep` passes all of them.
- **Recon is not proof either way** (coordinator note, Recon audit R-SA-12/R-SA-13): gem5-recon(-modded) has its own `flatIndex() == 16` skip on the *physical* destination (`taint_tracker.cc:59`), which hits about 1 in 220 allocations and is unrelated to xmm4. Its hits are the same stems with or without xmm routing. xmm4 adds no recon hit, and 9 of these stems already hit in the canonical recon campaign. These recon hits are all `store_forward` and are not analysed here.
- The baseline is a fresh concretization with today's code, not the June-3 `testsets_latest/STT_6` asm. Newer instruction tables pick different ops (e.g. `div`), so the files differ, but the GPR baseline is held 0/100 just like the canonical campaign.

### Example: inst-000082 (xmm4 vs GPR, grid point 0, `/work/stt`)

Asm (xmm4 variant, the access load's asm block):
```
__litmus_inst_000082_pc3:
	movq	(%rsi), %rax
	movq	%rax, %xmm4
	movq	$0, %rax
	movq	%xmm4, %rax
```
Pipeview / LSQ (xmm4 variant):
```
seq=605 pc=0x401c69.0 JNZ_I : rdip ...                 (mispredicted branch, held; wrip complete 2954000, retire 5461000)
seq=609 pc=0x401c70.0 MOV_R_M : ld rax, DS:[rsi]       issue=2950500 complete=2951000 retire=0   (access load)
seq=610 pc=0x401c73.0 MOVD_XMM_R : mov2fp %xmm4_low, rax  issue=2952000 complete=2953000
seq=611 pc=0x401c73.1 MOVD_XMM_R : lfpimm %xmm4_high, 0
seq=612 pc=0x401c78.0 MOV_R_I : limm rax, 0
seq=613 pc=0x401c7f.0 MOVD_R_XMM : mov2int rax, ...      issue=3007000 complete=3008000
seq=620 pc=0x401c91.0 MOV_R_M : ld r11, DS:[rax + rsi]  issue=3008000 complete=3008500   (transmitter)
3008500: system.cpu.iew.lsq.thread0: Executing load PC (0x401c91=>0x401c95).(0=>1), [sn:620]
3008500: system.cpu.iew.lsq.thread0: Doing memory access (normal load) for inst [sn:620] PC (0x401c91=>0x401c95).(0=>1)
3008500: system.cpu.iew.lsq.thread0: successfully sent out packet(s) for inst [sn:620]
```
check_ld: `lc_retire=2958500 < packet_tick=3008500 < fnc_retire=5461000`, branch 0x401c69 unresolved (resolve stall 5000 cycles; `branches_unresolved=True`), `cache_fate=reached_cache`, `issued_in_window=True` at all 3 grid points.

GPR variant, same stem: the transmitter `0x401c80` is inserted at 3007000 (`Inserting load PC (0x401c80=>0x401c84) [sn:616]`), never executes, and is squashed at 5455000 (`Load Instruction PC (0x401c80=>0x401c84) squashed, [sn:616]`). `cache_fate=never_executed`.

## Mechanism

1. `src/cpu/o3/rob_impl.hh:229` (`ROB::insertInst`, STT argProducer setup): `if (inst->srcRegIdx(i).index() == 16) // exclude zero register … continue;`. `RegId::index()` is the index *within the register class* (`cpu/reg_class.hh:164`), and the class is never checked.
2. Integer index 16 is the micro-code zero register (`arch/x86/registers.hh:82`), so skipping it there is intended. FP index 16 is `FLOATREG_XMM_LOW(4)`: `FLOATREG_XMM_BASE = FLOATREG_MMX_BASE + NumMMXRegs` with 8 MMX registers (`regs/float.hh:71`, `x86_traits.hh:57`) and `FLOATREG_XMM_LOW(i) = XMM_BASE + 2i` (`regs/float.hh:131-133`).
3. `movq %xmm4,%rax` (`66 48 0f 7e e0`) decodes to `MOVD(Edp,Vd)` → `MOVD_R_XMM` = one micro-op `mov2int reg, xmmlm` (`decoder/two_byte_opcodes.isa:694`, `general_purpose/data_transfer/move.py:360-362`), with FP source `xmmlm = FLOATREG_XMM_LOW(regm)` (`microasm.isa:95`), i.e. index 16. That source gets no argProducer, so `explicit_flow` (`rob_impl.hh:710-722`) never sees the tainted `mov2fp`, the copy-back is untainted, and so is the transmitter's address. The transmitter gets `fenceDelay(false)` (`lsq_unit_impl.hh:1013`) and executes.
4. **Why the gadget zeroes `%out` before the copy-back.** `Mov2int` also lists its integer destination as a source: its code has `DestReg = DestReg` in the else branch (`isa/microops/mediaop.isa:235-253`), and the ISA parser makes any operand read on a right-hand side a source. With a plain `movq %rax,%xmm4; movq %xmm4,%rax`, the copy-back would inherit the load's taint through the old `rax` (a normal integer source, not skipped), so it could never show the xmm4 bug. `movq $0,%rax` is `MOV_R_I` → `limm`, which is `LimmBig` (destination only) for dataSize ≥ 4 (`isa/microops/limmop.isa:116-124`), so the old `rax` becomes an untainted producer. `movq %rax,%xmm4` (`66 48 0f 6e`, `MOVD_XMM_R`) is `mov2fp xmml` + `lfpimm xmmh`. All paths are in `~/Documents/stanford/trippel/defense_src/stt_e3283b9/src/`, a copy of the `/work/stt` tree, whose `rob_impl.hh:229` matches it.

## Which builds carry the skip (grep of `src/cpu/o3/` on cafe2, 2026-11-08)

- `/work/stt`: `rob_impl.hh:229`, `srcRegIdx(i).index() == 16`. This is the bug.
- `/work/amulet/amulet-gem5-STT_AE-v1.1`: `rob_impl.hh:230`, the same line. Expected to have the same bug (not run here).
- `/work/gem5-recon-modded` and `/work/gem5-recon`: no `index() == 16` source skip. Both have `taint_tracker.cc:59` `if (regId->flatIndex() == 16) return;` on the physical destination register (Recon audit R-SA-12, a different bug).

## Verdict

**Real gem5 defense bug in STT** (an implementation bug, not a model, concretization or hook artifact). The paper's protection rule says taint follows every register data flow out of an access instruction (STT §6.2), and the Alloy protection-set clause agrees; the implementation breaks it for one FP register. Our pipeline found it: STT_6 tests concretized with the opt-in FPR routing (`fpr.xmm_regs=[4]`). The random-register FP-mode corpus (`specs/fanout/fp.json`) will hit it whenever a routed value lands in xmm4.

## Re-run

On cafe2, in `gem5_dev`, under `/tests/simspect_fixed_20261030`:
```
# testsets (already built): testsets_fpr_s1check/STT_6_fpr_{gpr,xmm3,xmm4}/mispredict_not_taken/{llvm,asm,ann}
bash testsets_fpr_s1check/run_s1check.sh            # 3 variants x {stt, reconmodded}, log testsets_fpr_s1check/run.log
python3 testsets_fpr_s1check/analyze.py             # per-variant counts -> testsets_fpr_s1check/summary.json
# one stem with traces kept: pipeline.py gem5 on a 1-stem stage with pipeline.keep_tmp=true (see testsets_fpr_s1check/_example/cfg.json);
# traces land in /tmp/gem5_<stem>_*/m5out/pipeview.txt; testsets_fpr_s1check/trace_ex.py extracts the lines above
```
Regenerate the three testsets on the Mac (add `--reg-naming-config '{"mode":"sorted"}'`: they predate random naming becoming the default): `batch_generate.py <xml> --kind --instruction-tables STAGE2_compilation/instruction_tables/instructions.jsonc --mode mispredict_not_taken [--fpr-config '{"enabled":true,"loads":"consumed","xmm_regs":[4]}']` (xmm3: `[3]`; baseline: no flag). Compile each `.ll` with `compile_annotate.py` in the container (`testsets_fpr_s1check/compile_all.sh`). The stem list is `testsets_fpr_s1check/stems.txt`. Campaigns: `results/STT_6_fpr_s1check_{gpr,xmm3,xmm4}_{stt,reconmodded}__2026110*`.

## Open

- Not yet run on amulet-STT (the same source line, so expected to leak).
- The 2 `executed_no_packet` stems (in window, no packet, never completed) were not analysed.
- No diagnostic bucket yet. If FP-mode campaigns on `/work/stt` are run, a `diag_stt_xmm4_skip.py` (real_bug phase) that buckets hits whose transmitter address chain passes a `mov2int` from xmm4 (ann `fpr.routes[].xmm == 4`) would keep them out of NEW.
