# Per-defense concretization vocabulary (Stage-2 instruction tables)

**Status:** draft proposal, 2026-11-07 (vocab-tables session). No `.als`, `parsexml.py`, existing instruction table, run config or git state was changed. New files only: `STAGE2_compilation/instruction_tables/proposed/today_superset.jsonc`, `today_taint.jsonc` (both loadable today) and `NEEDS_EMITTER_WORK.candidates.jsonc` (the rest; deliberately not loadable as a table). Related docs: [`CONCRETIZATION_PASSES.md`](CONCRETIZATION_PASSES.md) (pass 2 walkthrough), [`MODELS_AND_BUILDS.md`](MODELS_AND_BUILDS.md) (builds), [`../findings/mdsToRead/PROTECTION_SET_REEVAL.md`](../findings/mdsToRead/PROTECTION_SET_REEVAL.md) (what each paper protects).

## TL;DR

- **Tables alone can't give a richer vocabulary.** `pass5_emit_llvm` chooses its code by the concrete instruction's *name* and knows exactly 10 names: `load`, `store`, `bitnot`, `add`, `zsm`, `div`, `br_cond`, `br_uncond`, `br_bez`, `nop` (`parsexml.py:2144-2537`). Any other name emits only a pc label plus the comment "unknown concrete_instruction — skipped" (`:2535-2537`). `llvm_op` is only a label. On top of that, pass 2.5 overrides every branch choice: the transmitter branch always becomes `br_bez` and every other branch becomes `br_cond` (`:754-836`).
- **What works today with no code change:** `other_n` can reuse the existing multiply (`zsm`) and divide (`div`) as never-transmitting ALU ops. That gives two loadable drafts. `today_superset.jsonc` (other_n = bitnot, add, zsm, div) is for InvisiSpec, CleanupSpec, SpecLFB, DoM and Delay. `today_taint.jsonc` (other_n = bitnot, add, zsm) is for STT, ReCon, SPT and the STL variant. Both were run through the unmodified parsexml passes on 6 real-model XMLs and 458 draft-model XMLs, and through the `batch_generate.py` CLI on 4 XMLs: 0 errors, and every sampled `.ll` compiles for x86-64 Linux. **The effect is tiny:** the median number of distinct concretizations per instance stays 1 (the mean goes from 1.2 to 1.5). The reason is that ld and br records make up 83-91% of all records, while other_n is about 3%.
- **The real vocabulary needs approval-gated emitter work.** The proposed shared superset has 35 candidates (ld 10, str 5, br 5, other_n 13, other_x 2), and each per-defense table has 15 to 28. Every proposed x86 form was assembled in a scratch clang probe (`clang 21 --target=x86_64-unknown-linux-gnu -O2`).
- **Best value per unit of work:** (1) load widths `movzbq`/`movzwq`/`movl`, which matter for every defense: SPT keeps 4 partial-width taint bits per register, ReCon reveals only whole aligned words, and NDA's and AMuLeT's real gadgets use narrow loads. (2) Real ALU ops `mov`/`addq`/`xor`/`and`/`shl` for SPT's untaint algebra; today's `add` is really `leaq`, so no flag-setting ADD exists. (3) Store widths plus `store_imm`, for ReCon's conceal, SPT's shadow L1 and STL partial forwarding. (4) The load-op `addq (mem),%r` (ReCon §4.3; NDA works on micro-ops). (5) cmov from memory: every InvisiSpec and STT violation figure in AMuLeT uses one.
- **Test counts:** with the full per-defense tables, enumerating every combination gives a median of 25 to 128 concretizations per instance (STT reaches 12,800), which is too many for a 100k-instance testset. Two cheaper schemes: cover each candidate at least once (K ≈ 5-9 variants per instance), or vary one instruction at a time around a hit (≈ 9-17 variants). Several random draws per instance are possible today with no code change, through the interleave knob with `num_chains_choices: [0]`, but they produce duplicates.
- **Found along the way:** (a) `add` is emitted as LEA (`parsexml.py:2296`). (b) `zsm` and `div` put the pc marker on the leading `movq`, not on `imulq`/`idivq` (`:2321`, `:2376`; confirmed in a compiled object). So if an other_x were ever a transmitter, its address (`compile_annotate.py:280`) and check_other's timing (`check_other.py:22`) would measure the movq. This is dormant because no model's leakage function contains `Otherxs`. (c) In the gem5-recon STT source, the only instructions held are tainted loads and tainted *conditional* branches (`lsq_unit.cc:2079-2090`, `inst_queue.cc:1450-1456`, local source copy). Tainted indirect jumps, stores and mul/div are never held. (d) The probe_mem allocation checks for the literal names `load`/`store` (`parsexml.py:2063-2068`), so any new memory instruction must be added there.
- **Decisions for Anna:** V1-V9 at the bottom.

## How the vocabulary works today (from the code)

- **Loading.** `_load_instruction_tables` (`parsexml.py:493-510`) strips `//` and `/* */` comments and turns each `uses` into a set. A run picks its table with `paths.instruction_tables`: `pipeline.py:151` → `batch_generate --instruction-tables` → `reload_tables` (`parsexml.py:513-522`). The table file is copied into the testset's provenance tarball (`testsetgen.py:79`), so a testset built from a proposed table records which table it used.
- **Choice.** Pass 2 keeps the candidates whose `uses` contains every Alloy-specified slot (`parsexml.py:574`). If none fit, it falls back to all candidates (`:576-579`). It then picks one with `random.choice` (`:582`), seeded per stem and variant (`batch_generate.py:101-102`). The chosen name is visible in each `.ll` as a `; pc=N <atom> (<name>)` comment (`parsexml.py:2128`), but it is not written to `ann.json`.
- **`uses` does two jobs.** It is also how pass 3 decides which unspecified slots get a register or memory offset (`:1577-1589`, `:1600-1604`), and how pass 4 decides which slots get SSA names (`:1785-1807`). `_uses_for` looks the name up across all categories and takes the first match (`:1433-1441`). So a name can sit in several categories, but only with the same `uses` everywhere.
- **Slots.** Every Alloy record carries all six slots, specified or not (inreg0, inreg1, inaddr, inmem, outreg, outmem). In the sampled instances, a transmitter `ld` usually has only `inaddr` specified, while an access `ld` has `inmem` and `outreg`. So a candidate without an output, such as `prefetch`, is only offered for a load whose output Alloy leaves unused (normally the transmitter).
- **STL mode.** `_stl_arch_values` evaluates each instruction by name and raises `ValueError` on any name it does not know (`:1131-1168`), so the test is skipped. Every new candidate needs a case there before it can be used in `stl_bypass` mode.
- **Transmitter address.** The transmitter's address is the offset of its pc label (`compile_annotate.py:269-281`). The only exception is `br_x`, which is moved to the first conditional jump after the label (`find_branch_at_pc`, `:206`). So the transmitting instruction must be the first one after its label, and any setup instructions must come before it.
- **Interleave chains.** Chain steps added by `pass_interleave` use fixed names (`bitnot`, `add`, `load`, `store`; `parsexml.py:307-331`) and never draw from the table (V8).

## Shared superset (all candidates)

"Emits today" means pass 5 already has code for that name. Sources: STT = Yu 2019, SPT = Choudhary 2021, ReCon = Aimoniotis 2023 (HTML print, so sections only), InvisiSpec = Yan 2018, CleanupSpec = Saileshwar 2019, SpecLFB = Cheng 2024, AMuLeT = Fu 2025, unXpec = Li 2022 (all in `~/Documents/quail/sources/papers/`); NDA = Weisse 2019, DoM = Sakalis 2019, Doppelganger = Kvalsvik 2023 (fetched this session, see Sources). Page numbers are PDF pages. "G5" means the local gem5-recon source copy at `~/Documents/stanford/trippel/spectre-verify/run_asm/gem5-recon/src/arch/x86/isa/insts/general_purpose/`. Its x86 microcode is shared by every x86 build, but this copy was not checked to be identical to `/work/gem5-recon-modded`.

| kind | name | x86 form (AT&T) | uses | emits today | why it is in the vocabulary (source) |
|---|---|---|---|---|---|
| ld | `load` | `movq (%probe,%idx,1),%d` or `movq disp(%mem_base),%d` | inaddr inmem outreg | yes (`:2144-2183`) | baseline 64-bit load |
| ld | `load_zx8` | `movzbq (%probe,%idx,1),%d` | inaddr inmem outreg | no | NDA's Spectre-v1 example loads the secret and transmits with byte `movzx` (NDA p8 Fig.6); SPT tracks register taint in partial-width granules (p8 §7.2) and memory taint per byte (p9 §7.5); ReCon reveals only aligned whole words (§4.4); G5 `MOVZX_B_R_M` is a 1-byte ld micro-op plus zexti (`data_transfer/move.py:148-151`) |
| ld | `load_zx16` | `movzwq (...),%d` | inaddr inmem outreg | no | AMuLeT's InvisiSpec eviction violation uses `CMOVNBE SI, word ptr [R14+RAX]` (p10 Fig.4); SPT keeps an R[15:0] access mode (p8 §7.2) |
| ld | `load_32` | `movl (...),${0:k}` (writes the 32-bit name, zero-extends) | inaddr inmem outreg | no | AMuLeT's MSHR-contention violation uses `CMOVL EAX, dword ptr [...]` and `OR EDI, dword ptr [R14+RAX]` (p11 Fig.6); SPT R[31:0] (p8 §7.2) |
| ld | `load_sx32` | `movslq (...),%d` | inaddr inmem outreg | no (low priority) | G5 `MOVSXD_R_M` is a 4-byte ld plus sexti (`move.py:97-100`); with byte-level register taint, sign extension spreads one byte's taint into the upper bytes (my inference from SPT p8 §7.2, not a paper statement) |
| ld | `load_disp` | `movq 64(%probe,%idx,1),%d` | inaddr inmem outreg | no | ReCon: a load whose address is an earlier load's value plus an immediate offset still forms a valid load pair (§4.3) |
| ld | `load_idx8` | `movq (%probe,%idx,8),%d` | inaddr inmem outreg | no | ReCon: a "pointer" is an 8-byte address or an 8-byte integer index added to a constant base (§1) |
| ld | `load_op_add` | `movq $0,%d` ; label ; `addq (...),%d` | inaddr inmem outreg | no | ReCon: x86 arithmetic with a memory operand splits into micro-ops, one of them a load, and that load can form a load pair (§4.3); NDA marks *micro-ops* unsafe (p7 §5.1); AMuLeT p11 Fig.6; G5 `ADD_R_M` = ld + add (`arithmetic/add_and_subtract.py:120-124`); gem5-recon taints per micro-op (`src/cpu/o3/rename.cc:715`) |
| ld | `load_cmov` | flags ZF=1 ; `movq $0,%d` ; label ; `cmovzq (...),%d` | inaddr inmem outreg | no | every InvisiSpec and STT violation figure in AMuLeT uses CMOVcc with a memory source (p10 Fig.4, p11 Fig.6, p13 Fig.9); G5 `CMOVZ_R_M` always issues the ld micro-op, then two predicated moves (`data_transfer/conditional_move.py:43-48`) |
| ld | `prefetch` | `prefetcht0 (%probe,%idx,1)` | inaddr inmem | no (checker also unverified) | STT lists "prefetch instructions" among explicit channels (p4 §5.1); InvisiSpec handles software prefetch specially, with an invisible prefetch then an exposure (p8 §VI-B); G5 `PREFETCH_T0_M` is `ld t0 ... dataSize=1, prefetch=True` (`cache_and_memory_management.py:48-51`) |
| str | `store` | `movq %s,(...)` | inreg0 inaddr outmem | yes (`:2185-2256`) | baseline |
| str | `store8` / `store16` / `store32` | `movb ${0:b}` / `movw ${0:w}` / `movl ${0:k}` to `(...)` | inreg0 inaddr outmem | no | ReCon: conceal works at any granularity, and writing any part of a revealed word conceals the whole word (§4.4); SPT: store-data taint overwrites the written bytes' taint (p9 §7.5); SPT's evaluated transmitters are loads and stores (p10 §9.1) and `SPT_6_oneLP.als:344` has `Stores.inaddr`; a narrow store aliasing a wide load is the STL partial-forwarding case (gem5 behaviour not checked) |
| str | `store_imm` | `movq $0,(...)` | inaddr outmem | one-line alias | SPT: untainted store data written to the L1D clears that range's taint (p8 §6.8, rule 1); ReCon: a performed store conceals (§4.4.1). The immediate-store code already exists (`:2235-2238`, `:2254-2256`); only the name needs routing to it |
| br | `br_cond` / `br_bez` / `br_uncond` | `testq ; jne` / `testq ; je` | inreg0 | yes, but pass 2.5 forces the choice | baseline |
| br | `br_cmp` | label ; `cmpq $1,%c ; jb` (inline asm goto) | inreg0 | no (pass 2.5 + asm goto) | NDA's gadget bounds check is `cmp ; jae` (p8 Fig.6), as is STT's `if (addr < 10)` (p2 Fig.1). SPT declassifies a branch's operands when it becomes non-speculative (p6 §6.6), but allows backward untaint only through MOV and invertible ops (p7); a `cmp` between the tainted value and the jcc is where an over-eager untaint would show. LLVM rewrote an IR `icmp ult x,1` into `testq ; je` in the probe, so this form must be inline asm goto |
| br | `br_indirect` | `jmpq *%t` | inreg0 | no (large) | NDA: "Branch instructions include all variants of jmp, call, and ret" (p6 §4.1); DoM's C-shadow covers jumps with unknown targets (p3 §3); SpecLFB marks jumps unsafe (p8 §6.1); gem5-recon STT holds only tainted `isCondCtrl()` branches (`inst_queue.cc:1450-1456`), and G5 `JMP_R` is `.control_indirect` (`control_transfer/jump.py:49-53`) |
| other_n | `bitnot` | `movq ; notq` | inreg0 outreg | yes (`:2258-2280`) | invertible unary op (SPT p5 §5 lists NOT) |
| other_n | `add` | `leaq (a,b),d` | inreg0 inreg1 outreg | yes (`:2282-2303`) | this is actually an LEA, not ADD |
| other_n | `zsm` | `movq ; imulq` | inreg0 inreg1 outreg | yes (reused) | non-invertible binary op: SPT must not untaint backward through it (p7) |
| other_n | `div` | non-transmitter `idivq` form (divisor ORed with 1) | inreg0 inreg1 outreg | yes (reused) | an op that can raise an exception: it casts a DoM E-shadow (p3 §3) and opens SpecLFB's exception-check window (p8 §5). Not proposed for taint defenses (V3) |
| other_n | `mov` | `movq a,d` | inreg0 outreg | no | SPT backward rule 1: register MOV (p7) |
| other_n | `addq` | `movq a,d ; addq b,d` | inreg0 inreg1 outreg | no | SPT backward rule 2: invertible arithmetic, "e.g., ADD" (p7) |
| other_n | `sub` | `movq ; subq` | inreg0 inreg1 outreg | no | invertible (SPT p7: r1 = r0 − r2) |
| other_n | `xor` | `movq ; xorq` | inreg0 inreg1 outreg | no | SPT: the algebra covers OR, XOR, NOT, ADD (p2, p5 §5) |
| other_n | `and` / `or` | `movq ; andq` / `orq` | inreg0 inreg1 outreg | no | AND is SPT's GLIFT example (p4-5 Fig.2), and the evaluated rules "do not apply the GLIFT insights" (p7), so no backward untaint is allowed through these |
| other_n | `shl_imm` | `movq ; shlq $9` | inreg0 outreg | no | NDA's gadget preprocess step `shl eax,0x9` (p8 Fig.6 line 10) |
| other_n | `lea_scaled` | `leaq (a,b,8),d` | inreg0 inreg1 outreg | no | NDA's gadget address calculation `lea rax,[r12+rbx*1]` (p8 Fig.6 line 8); G5 LEA is a single micro-op (`load_effective_address.py:37-39`); `parsexml.py:2042-2045` notes that gem5's Lea-merge creates taint |
| other_n | `mov_imm` | `movq $17,d` | outreg | no | SPT untaints the outputs of "load immediate" instructions (p6 §6.5); G5 `MOV_R_I` = limm (`move.py:74-76`) |
| other_x | `zsm`, `div` | as today | inreg0 inreg1 outreg | yes | dormant: no model has `Otherxs` in its leakage function (`STT_6.als:327-328`, `Recon_6.als:319-320`, `SPT_6_oneLP.als:342-344`). The marker fix (G8) is needed before that changes |

Not recommended, but listed in the candidates file: `zero_idiom` (`xorq d,d`, V6); register-to-register `cmov_rr` (no defense paper read here singles it out); RMW and `lock` RMW (`xorq %r,(mem)`, `lock andl`), which AMuLeT uses but which mix load, ALU and store in one instruction (V7); `clflush`, which CleanupSpec delays (p7 §3.5) but whose gem5 macro-op includes an `mfence` (G5 `cache_and_memory_management.py:59-62`) that would close the speculative window; `div32`/`udiv` (that their latency differs is from memory, unverified).

## Per-defense tables

Each table lists, per kind, the "today" set (loadable now) and the proposed full set (needs emitter work). Counts are the number of candidates. Branch rows ignore `br_uncond`, which pass 2.5 always upgrades.

### STT (units stt_on_stt, stt_on_recon, stt_on_spt; model STT_6)

What the paper says matters: STT taints the outputs of speculative access instructions (loads). An output is tainted if any input is tainted, and STT delays transmitters with tainted operands (p6 §6.1-6.3). A transmitter is any instruction "whose execution creates operand-dependent resource usage" (p6 §6.1.1). Examples are memory instructions, variable-latency arithmetic and prefetch instructions (p4 §5.1). "Classifying only loads as transmitters will block memory system-related explicit covert channels." Stores count as transmitters unless they invalidate only at retirement (p5 §6.1). Implicit channels come from explicit branches and from implicit branches such as store-to-load forwarding (p7-8 §6.4). The evaluation used loads as the transmitters (p12 §9.2). Build facts: gem5-recon STT holds tainted loads and tainted conditional branches only (`lsq_unit.cc:2079-2090`, `inst_queue.cc:1450-1456`). AMuLeT found that STT's gem5 lets tainted speculative stores fill the D-TLB (p13 §4.8, KV3, previously known from DOLMA).

| kind | today | proposed | defense-specific reason |
|---|---|---|---|
| ld | load (1) | load, load_zx8, load_zx16, load_32, load_disp, load_idx8, load_op_add, load_cmov, prefetch (9) | widths and load-ops test that taint and holding happen per micro-op, whatever the width; cmov is AMuLeT's STT violation shape (p13 Fig.9); prefetch is a transmitter the paper lists (p4) |
| str | store (1) | store, store8, store16, store32, store_imm (5) | stores are not STT_6 transmitters, but AMuLeT KV3 shows tainted stores reach the TLB; store widths change the STL implicit-branch predicate (p8 §6.4.2) |
| br | forced (1) | + br_cmp now, br_indirect later (2) | explicit branches are all control flow (p7 §6.4.1), but gem5-recon holds only conditional ones |
| other_n | bitnot, add, zsm (3) | + mov, addq, xor, and, shl_imm, lea_scaled, mov_imm (10) | STT propagates taint the same way for every op (p6), so variety here only catches per-opcode propagation gaps (for example the LEA merge) |
| other_x | zsm, div (2) | same (2) | dormant |

### ReCon (recon_on_recon on Recon_6; recon_otb on STT_6_multisource)

What the paper says matters: ReCon reveals a value when a committed pair of loads dereferences it. The second load's address must come directly from the first load's destination register, "without intermediaries" (§4.1, §4.3). An immediate offset on either load still counts (§4.3). A load micro-op inside an x86 load-op instruction counts (§4.3). A "pointer" is an 8-byte address or 8-byte index (§1). Reveal works only for aligned whole words, while conceal works at any granularity (§4.4). Stores conceal while in the store queue and store buffer (§4.4.2). ReCon is layered on STT or NDA (§3.1). Build: gem5-recon, which has a reveal-bit / allow-leaked path (`lsq_unit.cc:194-210`, `:242-253`).

| kind | today | proposed | defense-specific reason |
|---|---|---|---|
| ld | load (1) | same 9 as STT; priorities are load_disp, load_idx8, load_op_add and the widths | each is a stated case or a boundary case of the load-pair detector: offset (§4.3), base plus index (§1), micro-op load (§4.3), a narrow or unaligned read of a revealed word (§4.4) |
| str | store (1) | store, store8, store16, store32, store_imm (5) | a partial store must conceal the whole word (§4.4); store_imm conceals with public data |
| br | forced (1) | + br_cmp (2) | as STT |
| other_n | bitnot, add, zsm (3) | same 10 as STT | a `mov` or `lea` between the two loads breaks the direct dependence (§4.3), so it must *not* reveal: a boundary test |
| other_x | zsm, div (2) | same (2) | dormant |

### SPT (spt_fence, spt_variants; model SPT_6_oneLP)

What the paper says matters: transmitters are memory, control-flow and variable-time arithmetic instructions (p2 §2.1), and the evaluated ones are loads and stores (p10 §9.1). The untaint algebra depends on the instruction type. Forward: if all operands are untainted, the output is untainted, except for loads (p7). Backward: only register MOV (rule 1) and invertible arithmetic such as ADD (rule 2), with GLIFT not applied (p7). Load-immediate outputs are untainted; the `r − r` zero idiom is "not currently exploit[ed]" (p6 §6.5). Transmitter and branch operands are declassified when the instruction becomes non-speculative (p6 §6.6). Untaint crosses store-to-load forwarding only under STLPublic (p7-8 §6.7). In the L1D, untainted store data clears taint and a load ANDs the taints (p8 §6.8). Register taint is kept in 4 granules, R[7:0], R[15:8], R[31:16] and R[63:32] (p8 §7.2); the shadow L1 is byte-granular (p9 §7.5). Build knobs `--fwdUntaint` and `--bwdUntaint` ([`MODELS_AND_BUILDS.md`](MODELS_AND_BUILDS.md):143). This matches audit item SPT-2 ([`../findings/audits/2026-10-28/APPROVALS.md`](../findings/audits/2026-10-28/APPROVALS.md):18).

| kind | today | proposed | defense-specific reason |
|---|---|---|---|
| ld | load (1) | load, load_zx8, load_zx16, load_32, load_sx32, load_disp, load_op_add (7) | narrow loads read and write partial taint granules; load_op_add combines a load and an ALU op in one macro-op |
| str | store (1) | store, store8, store16, store32, store_imm (5) | the store is a transmitter in SPT_6_oneLP (`:344`); widths exercise the byte-granular shadow L1; store_imm exercises §6.8 rule 1 |
| br | forced (1) | + br_cmp (2) | a cmp is neither MOV nor invertible, so declassifying the branch must not untaint the cmp's inputs (p6 §6.6 + p7) |
| other_n | bitnot, add, zsm (3) | mov (rule 1); addq, sub, xor, bitnot (rule 2, invertible); and, or, shl_imm, zsm (non-invertible: no backward untaint); add and lea_scaled (LEA, classification unknown); mov_imm (§6.5) (12) | this is the main reason SPT needs a richer table: each class has a different correct untaint behaviour, so an over-eager untaint bug shows up per class |
| other_x | zsm, div (2) | same (2) | div stays out of other_n because SPT counts variable-time arithmetic as a transmitter (p2) |

### InvisiSpec (invisispec_on_amulet; model STT_6)

What the paper says matters: only loads; "we limit ourselves to load instructions" (p4 §IV). Unsafe speculative loads fill a speculative buffer and are validated or exposed at the visibility point (p4-5 §V). Software prefetches get an invisible prefetch, then an exposure (p8 §VI-B). AMuLeT found UV1, speculative L1D evictions, whose test uses a word-sized cmov load plus qword and byte RMW instructions (p10 Fig.4), and UV2, MSHR contention, which uses a dword cmov load, `lock and` and a dword load-op (p11 Fig.6).

| kind | today | proposed | defense-specific reason |
|---|---|---|---|
| ld | load (1) | load, load_zx8, load_zx16, load_32, load_op_add, load_cmov, prefetch (7) | AMuLeT's violating shapes plus the paper's prefetch path |
| str | store (1) | store, store8, store16, store32 (4) | InvisiSpec does not make stores speculative, but they shape the cache state that the eviction bug leaks through (AMuLeT UV1) |
| br | forced (1) | forced (1) | — |
| other_n | bitnot, add, zsm, div (4) | + mov, xor, shl_imm (7) | ALU ops are never protected here; they only shape the dataflow |
| other_x | zsm, div (2) | same (2) | — |

### CleanupSpec (cleanupspec_on_amulet; model STT_6)

What the paper says matters: undo-based. It uses random replacement in L1, and on a squash it invalidates and restores the lines that were installed (p5-6 §3). It delays a transient `clflush` (p7 §3.5) and assumes hardware prefetching is off (p3 §2.1). unXpec shows the rollback time grows with the amount of transient cache change (unXpec p2).

| kind | today | proposed | defense-specific reason |
|---|---|---|---|
| ld | load (1) | load, load_zx8, load_zx16, load_32, load_op_add, load_cmov, prefetch (7) | the paper says nothing about *software* prefetch, which is a possible gap; the other forms are AMuLeT's shapes |
| str | store (1) | store, store8, store16, store32 (4) | — |
| br | forced (1) | forced (1) | — |
| other_n | bitnot, add, zsm, div (4) | same (4) | — |
| other_x | zsm, div (2) | same (2) | — |

### SpecLFB (speclfb_on_amulet; model STT_6)

What the paper says matters: it protects MUSLs, the unsafe speculative loads that miss, using the line fill buffer (p7). An instruction marks later loads unsafe if it uses the load queue or the store queue, or if it is a branch or jump (p8 §6.1). Instructions that can raise exceptions keep later misses unsafe until the exception check (p8 §5). AMuLeT found an undocumented optimization that drops protection for the first speculative load, triggered by a plain `MOV RAX, ptr [R14+RBX]` (p13 Fig.8).

| kind | today | proposed | defense-specific reason |
|---|---|---|---|
| ld | load (1) | load, load_zx8, load_zx16, load_32, load_op_add, load_cmov, prefetch (7) | every load micro-op form should go through the MUSL path |
| str | store (1) | store (1) | — |
| br | forced (1) | forced (1) | — |
| other_n | bitnot, add, zsm, div (4) | same (4) | div opens the exception-check window (p8 §5) |
| other_x | zsm, div (2) | same (2) | — |

### DoM and NDA (units dom and delay; gem5-recon --scheme=3 and =1, scheme 1 = NDA, code enum Delay; model STT_6)

What the paper says matters: speculative L1 hits proceed "provided that we do not affect the L1 replacement state or perform any prefetches"; misses are delayed (or value-predicted). Only loads are covered, because "stores are kept hidden in the store buffer until they are committed" (DoM p2 §1). Four shadow types: E (memory ops with unknown addresses, arithmetic and any other instruction that can raise an exception), C (branches and jumps), D (stores with unresolved addresses) and M (older loads under TSO) (p3 §3). Build: gem5-recon DoM marks speculative packets L1-only (`lsq.cc:1443-1446`) and holds conditional branches that are not the oldest shadow (`inst_queue.cc:1459-1465`). Delay holds back the completion of speculative loads (`lsq_unit.cc:194-210`).

| kind | today | proposed | defense-specific reason |
|---|---|---|---|
| ld | load (1) | load, load_zx8, load_zx16, load_32, load_op_add, load_cmov, prefetch (7) | checks that the L1-only rule covers every load micro-op form; for prefetch, the gem5 L1-only condition skips `UNPREDICTABLE` requests, and whether prefetches are flagged that way was not checked |
| str | store (1) | store, store8, store16, store32 (4) | stores are D-shadow sources |
| br | forced (1) | forced (1) | — |
| other_n | bitnot, add, zsm, div (4) | + mov, shl_imm (6) | div casts an E-shadow |
| other_x | zsm, div (2) | same (2) | — |

### STL variant (STT_6_stl on gem5-recon-stl, mode stl_bypass)

What matters: store-to-load forwarding is an implicit branch whose predicate checks that every older in-flight store does not alias with the load (STT p8 §6.4.2). See also ReCon §4.5 and Doppelganger p5. Every candidate also needs a `_stl_arch_values` case (`parsexml.py:1131-1168`), and store candidates need the retarget path (`:2185-2215`).

| kind | today | proposed | reason |
|---|---|---|---|
| ld | load (1) | load, load_zx8, load_zx16, load_32, load_op_add (5) | a wide load fed by a narrow store, and the reverse, are the partial-forwarding cases |
| str | store (1) | store, store8, store16, store32, store_imm (5) | as above; store_imm forwards a public value |
| br | forced (1) | forced (1) | the mode requires every branch to be resolved (`:707-719`) |
| other_n | bitnot, add, zsm (3) | + mov, addq, xor (6) | — |
| other_x | zsm, div (2) | same (2) | — |

### NDA and Doppelganger (both DO have builds, see the V9 correction; NDA uses the DoM/NDA table above, Doppelganger has no table yet)

Neither has a build in `specs/gem5_builds.json`; `documentation/docs/defenses.md` lists NDA as "no" and Doppelganger as "closed source". NDA's strict propagation withholds the result of every micro-op dispatched after an unresolved branch or store (p7 §5.1). Permissive propagation withholds only loads, and "non-load micro-ops are marked safe" (p9 §5.2). Load restriction keeps loads (and `rdmsr`) unsafe until they reach the ROB head (p7 §5). NDA's Spectre-v1 example (p8 Fig.6) is the best paper source here for the canonical x86 gadget forms: byte `movzx` loads, `lea`, `shl` and `cmp`/`jae`. The closest build is Delay (scheme 1); this is an inference, not verified (ReCon §2.1 and §3.1 evaluate "NDA permissive propagation", and the build offers Unsafe/Delay/STT/DoM). Doppelganger predicts the addresses of dependent loads with a PC-indexed stride predictor trained on committed addresses (p1-2), and issues them independently of store-to-load forwarding (p5). For it, address patterns (load_disp, load_idx8) matter more than opcodes.

## RMW instructions: brief (2026-11-08, hooks-v2 session)

**What an RMW is.** An x86 read-modify-write instruction loads from memory, computes, and stores back to the same address in one instruction (e.g. `orq %rdx,(%rdi)`, `addq $1,(%rax)`, `xchg`, `lock andl`). gem5 splits it into micro-ops: a load-with-store-intent (`ldst`), an ALU op, and a store. STT_6's concretized tests contain **0** RMW instructions (CleanupSpec agent count over the 150k `mispredict_not_taken` asm files, 2026-11-08). Today's tables emit loads and stores only as separate `mov`s (V7 above).

**Why it matters now.**
- **CleanupSpec UV3 is reachable only through an RMW.** On the 2026-11-08 demo `uv3rmw` (cafe2 `/tests/simspect_fixed_20261030/results/STT_6_cleanupspec_v2hooks__20261107/demos/`):
  - a speculative `orq %rdx,(%rdi)` under a held mispredict issues its `ldst` as a write request and installs the line at execute (`L1D:fill … req=st:msg=ST:ev=Store:st=NP:nst=IM`);
  - CleanupSpec then skips the undo (`cleanup_skip why=nohitinfo`), because `Sequencer::writeCallback` sets no L2Hit/L2Miss, so `lsq_unit_impl.hh:2584-2589` has no hit info;
  - check_footprint flags it.
- **Plain `mov` stores never touch the cache before commit** on these builds (control `uv3st`), which is why the June note called UV3 unreachable.
- **AMuLeT's own InvisiSpec findings also use RMWs:** UV1 uses qword and byte RMWs (AMuLeT p10 Fig. 4) and UV2 uses `lock and` (p11 Fig. 6), per the InvisiSpec row above.

**Open questions (the RMW agent below answers these):**
1. On each build, does the speculative RMW's load half get the defense's load protection (InvisiSpec SpecLoad, SpecLFB USL, STT taint, CleanupSpec undo), or does it bypass it as a write request? A bypass would be a new bug class.
2. Can generation produce RMWs without a model change? For example, a concretization peephole that fuses an Alloy `ld → other → str` chain on one address into one RMW, or llc folding a load/op/store on one pointer. Or does it need a new Alloy kind (a `.als` change, Anna's call)?
3. Which defenses' claims make RMWs in-scope stimulus?

### RMW agent findings (2026-11-08)

**Bottom line.** On every build except CleanupSpec, a speculative RMW's load half gets the same protection as a plain `mov` load. The A/B demos show identical hook lines for the load and for the RMW's `ldst`. The only divergence is CleanupSpec, and it is the known UV3 (AMuLeT §4.6 p11), not a new bug class. `lock` RMWs and `xchg mem` never execute speculatively on any of these gem5 trees. RMWs are in scope for CleanupSpec (strongly) and STT (by the paper's own assumption about stores), and are a low-value check for InvisiSpec and SpecLFB. The pipeline makes no RMWs today because pass 5 hard-codes each `ld`/`str` as its own inline-asm `movq`. A cheap no-`.als` route exists: concretize a transmitter load whose result is unused as a value-neutral RMW. Every one of STT_6's 66,512 `ld` transmitters qualifies.

**How gem5 classifies the RMW load half (source, cafe2).** `OR_M_R`/`OR_M_I` expand to `ldst t1; or; st t1` (InvisiSpec tree `src/arch/x86/isa/insts/general_purpose/logical.py:42-47,80-84`). `ldst` is a `LoadOp`, so `isLoad()` is true and the LSQ issues it as a load. Its only difference from `ld` is a request flag. In the old trees (InvisiSpec, CleanupSpec, `/work/stt`) that flag is `StoreCheck<<FlagShift` (`arch/x86/isa/microops/ldstop.isa:483-485`). In the newer trees (SpecLFB, gem5-recon-modded) it is `Request::READ_MODIFY_WRITE` (`ldstop.isa:505-507`). The flag matters only in the Ruby `Sequencer::makeRequest`, which turns a non-spec read carrying it into `RMW_Read` with secondary type `ST`, i.e. an exclusive GETX (InvisiSpec `mem/ruby/system/Sequencer.cc:852-863`, CleanupSpec `Sequencer.cc:984-993`). The classic caches (SpecLFB, STT, Recon) ignore the flag, so there it is a plain `ReadReq`/`ReadSharedReq`. The locked forms `ldstl` are defined with `nonSpec=True` → `IsNonSpeculative` (`ldstop.isa:486-489,312-313`; SpecLFB `:508-511`). `XCHG_M_R` is `mfence; ldstl; stul; mfence` (`data_transfer/xchg.py:70-76`). So `lock` RMWs and `xchg` wait for the ROB head and are useless as speculative stimulus.

**Per-build answer (demos: cafe2 `/work/amulet/rmw_probe/`, README.txt there, log `probe.log`, 24 runs, 0 errors).** Each gadget does a committed warm load to the page, then a branch that is really taken but forced predicted not-taken and held unresolved for 2000 cycles, then the probe on a cold line. The probe is A = `movq (%rdi),%rax` or B = `orq %rdx,(%rdi)`, plus `lock orq` on InvisiSpec. For STT and Recon the probe address is tainted by a speculative load (`tld`/`trmw`). Flags: InvisiSpec ISX/FSX, CleanupSpec CSX + `--fnc-commit-stall-cycles=150`, SpecLFB `--l2cache` (all as in `gem5-hooks/verify/run_all_verify_v2.sh`), STT/Recon `--caches --scheme=2` (as `results/STT_6_sttbuild`, `results/Recon_6` run configs).

| build | RMW load half protected? | source evidence | demo result (ld vs rmw) |
|---|---|---|---|
| InvisiSpec Spectre | yes, same as a load | `cpu/o3/lsq_unit.hh:881-901` picks `createReadSpec` from `isInvisibleSpec && !readyToExpose()` only; `Sequencer.cc:740-787` handles `isSpec()` before the StoreCheck branch | identical: `LSQ:issue req=specld` → `L1D:miss msg=SPEC_LD ev=SpecLoad` → `L2 GETSPEC` → `SB:buf_fill` → `SB:buf_release why=squash`; no L1D/L2 fill. The RMW adds only its `st` micro-op's `DTLB:hit req=st spec=0` (+`repl_touch`), which a plain store also does (DTLB LRU is the known gap in `wiki/findings/audits/2026-10-28/invisispec_flagged_events_triage.md` §1). `lock orq`: never issued in the window |
| InvisiSpec Futuristic | yes | same | without a fence the warm load's DTLB fill is deferred, so both probes fault (`why=spec_miss_fault`) and never issue. With `mfence` (`fld`/`frmw`): identical SPEC_LD/SB lines as above |
| CleanupSpec | **no: the undo is skipped (known UV3)** | ldst → `RMW_Read`/GETX; `writeCallback` (`Sequencer.cc:443-480`) sets only `L1Hit`, never L2Hit/L2Miss, so `lsq_unit_impl.hh:2584-2589` logs `nohitinfo` | ld: `L1D:fill … msg=DATA_EXCLUSIVE`, then after the squash `L1D:cleanup_inv` + `L2:cleanup_inv` (undone). rmw: `165000:L1D:fill … req=st:msg=ST:ev=Store:st=NP:nst=IM`, `L2:fill … msg=GETX`, `248000:L1D:repl_touch … st=IM:nst=M`, then `1165500:L1D:cleanup_skip … why=nohitinfo` (line left in L1 M and in L2) |
| SpecLFB | yes, same as a load (and equally subject to UV6) | `cpu/o3/lsq.cc:1050-1066` sets USL when `isUnsafe() && !isStore()`, and `ldst` is not a store | identical flag/issue lines: the first speculative access gets `unsafe=0 prevnounsafe=1 usl=0` and fills L1D (the UV6 first-load optimization) whether it is a ld or an rmw; later instances get `usl=1` and `bounced=1`. `rmw2` (a load before the RMW) behaves like `ld2` |
| STT (`/work/stt`) | yes: tainted RMW delayed | `cpu/base_dyn_inst.hh:675-676` `isAccess()`/`isTransmit()` = `isLoad()`; delay in `lsq_unit_impl.hh:1013` | tainted ld and tainted rmw: LSQ insert, never `Executing load`, squashed at 1155000; the Cache-flag rerun shows no dcache access to the probe line. An untainted rmw executes its load half speculatively, as expected |
| Recon-STT (gem5-recon-modded) | yes | `cpu/o3/rename.cc:715-720` taints `isLoad() && isSpeculative()`; `lsq_unit.cc:2095-2105` puts tainted loads in the delay unit | tainted ld and rmw: `STL_CHECK isTainted=1`, `delay_unit.insertedTaintedLoads` > 0, no dcache access to the probe line (Cache rerun). Note: "Doing memory access" is printed *before* the taint check (`lsq_unit.cc:2077` vs `:2095`), so it is not evidence of an access. The demo annotation needed the `branch_pc_addr_hex` key, since this se.py ignores `branch_addr` (`configs/example/se.py:109-116`) |

**Candidate bug: none new.** The CleanupSpec RMW footprint is UV3. AMuLeT describes UV3 as "speculative stores" (§4.6 p11, Listing 3/Fig. 7 "WriteCallback() for Spec Store L1Hit: 0, L2Hit: 0, L2Miss: 0"). On these gem5 trees the only store-side request that reaches the cache before commit is an RMW's `ldst` (control `uv3st` shows no pre-commit access), so AMuLeT's UV3 tests must have been RMWs too (inference). Adversarial check: it is not a checker artifact, since the plain-load control in the same gadget gets `cleanup_inv` at L1 and L2. It is not a timing artifact, since the fill happens 900k ticks before the release. One open hypothesis, **unverified**: AMuLeT's fix (writeCallback metadata) would undo the local install. But a speculative GETX also invalidates other cores' copies, which CleanupSpec claims never happens ("RFOs are issued non-speculatively", p8 §4). A single-core SE run cannot show that; a 2-core run could.

**Scope per paper (from the PDFs in `~/Documents/quail/sources/papers/`).**

- **InvisiSpec:** loads only, "we limit ourselves to load instructions" (p4 §IV). "Since an atomic instruction involves a write, InvisiSpec does not execute them speculatively" (p9 §VI-E.2). Stores retire into the write buffer and update the cache at commit (p2, background section). So an RMW's load half is a USL and in scope (it is handled), and the store half is out of scope. Value of RMW stimulus: low (AMuLeT UV1/UV2 use RMWs only to shape cache state).
- **CleanupSpec:** the threat model assumes "the transient change is initiated with a speculative read" (p8 §4). The paper also states RFOs are non-speculative (p8 §4) and handles coherence downgrades (p5 §3). A speculative RMW breaks that stated invariant, so RMWs are **in scope and the highest-value stimulus**.
- **SpecLFB:** protects MUSLs, unsafe speculative loads that miss (p7). Load-queue/store-queue users only mark later loads unsafe (p8 §6.1). It excludes TLB channels (p6). The RMW load half is in scope and handled; the store half is out of scope.
- **STT:** "We assume that stores trigger a cache coherence invalidation only on retirement, or else are defined as transmitters" (p5 §6.1). "loads and stores access memory only if their address argument is untainted" (p9 §6.4). So an RMW's address is in scope as a transmitter, and both STT builds already treat it as one.
- **AMuLeT:** uses RMWs in UV1 (Fig. 4 p10), UV2 (`lock and`, Fig. 6 p11) and UV3 (§4.6 p11).

**Why STT_6 has 0 RMWs.** The cause is the emitter. The instruction tables list one `ld` candidate (`load`) and one `str` candidate (`store`) (`STAGE2_compilation/instruction_tables/instructions.jsonc:14-26`). Pass 5 then emits each as its own `call … asm sideeffect "…movq …"` with the pc marker labels inside the asm string (`STAGE2_compilation/parsexml.py:2144-2251`). clang `-O2` (`compile_annotate.py:96-99`) cannot fold across opaque inline asm, so no llc option can create an RMW. The model is a second limit: a full scan of STT_6's 100,000 base instances (`/work/amulet/rmw_probe/scan_STT_6.txt`) finds 15,285 with both a ld and a str. 1,222 of these have a ld before a str on the same location (STT_6 has one `Mem_s` atom, so every memory operand concretizes to the same slot, e.g. `inst-003537` pc2 `movq (%rsi),%rax` … pc4 `movq %r12,(%rsi)`). But **0** have the data chain ld.outreg → other → str.inreg, and 0 have even ld → str. As with OTB, "absent in the capped enumeration" ≠ "the model can't". A forcing predicate would show whether the chain is SAT. The transmitter scan (`scan_STT_6_xmit.txt`) shows all 66,512 `ld` transmitters address through `inaddr`, and none has an rf consumer of its outreg.

**Generation options (costs; Anna's call).**

- **(a) Peephole fusing `ld X → other → str X`:** pass 5 detects the chain and emits one `opq %src,(addr)`, with all three pc markers on that instruction and the xmit pc pointing at it. Cost: a medium `parsexml.py` change (approval-gated). It also needs rules for when fusion is legal: all three in one commit class, adjacent, intermediate registers dead. **Yield on STT_6 today: 0 tests.** It needs a forcing predicate or a new enumeration (a model/config change) to produce anything.
- **(b) llc folding:** this needs the emitter to drop per-pc inline asm for plain IR loads and stores. That loses the pc markers and the register pinning the annotations and checkers depend on, and whether x86 isel folds `volatile` accesses into RMW is unverified (from memory). Cost: high. Not recommended.
- **(c) New Alloy kind `rmw` (`.als` change):** the most faithful option. An RMW is an access (its loaded value feeds the store data, which can then STL-forward a tainted value) and a transmitter (its address) in one instruction, with atomic commit. Cost: a model change on the shared skeleton and every model, plus emitter, tables, annotations and a regen. Anna's call.
- **(d) Value-neutral RMW as a transmitter-load variant:** add an instruction-table candidate for `ld` transmitters whose outreg has no consumer, e.g. `load_rmw_or0` = `orq $0,(probe_mem,idx,1)` (gem5 `OR_M_I` = `limm; ldst; or; st`). The architectural value is unchanged, the address dependency is the same, the xmit pc and marker stay on the one instruction, `.ann.json` is unchanged, and `check_ld` still sees the `ldst`'s "Executing load". Cost: a small `parsexml.py` pass-5 branch plus a table entry, both approval-gated, and no `.als` change. Applies to all 66,512 STT_6 `ld`-xmit tests (or a sampled subset).
  - What changes or breaks: the RMW's store micro-op enters the store queue, so a younger load to the same address in the window can now forward from it, or the store can raise memory-order squashes. It writes (dirties) the line if the xmit ever commits. It drops the `=&{phys}` pinning of the unused outreg (possible register-allocation drift). On CleanupSpec every such test would hit UV3, so it needs a `diag_uv3_rmw` known-cause bucket before it runs there.

**Recommendation (a recommendation, not a decision).** Option (d) as an opt-in table variant, run first as a small CleanupSpec + STT sample with a UV3 diagnostic, because it is the only route that yields RMW tests without touching a `.als`. Keep (c) on the list if RMW-as-access matters for STL/taint. Skip (b), and skip `lock`/`xchg` forms entirely, since gem5 never runs them speculatively. This sharpens V7: leaving RMWs out costs CleanupSpec UV3 coverage, and no other build has an RMW-specific gap.

## Effect on test counts

"Combos" is the product over an instance's records of the number of valid candidates, with the uses filter applied as in pass 2 and branches counted as 1 unless `br_cmp` is in the table. Corpora: 6 real-model XMLs (DEMO, two bug XMLs, two STT_6 and two Recon_6 two-phase drafts) and 458 draft-model XMLs (`results/twophase_stage1_2026-11-03/tiny/out_{STT,Recon}_RIonly_N3`, `out_SPT_inuse_N5`). In the 458-XML corpus, records split as ld 750, br 830, str 60, other_x 52, other_n 47. "Cover-each K" is the number of variants needed so that every candidate of every record appears at least once (the per-instance maximum of the valid counts). "OFAT" means varying one instruction at a time around a fixed instance: 1 + Σ(valid − 1).

| table | sizes ld/str/br/other_n/other_x | combos per instance, real 6 (median / mean / max) | combos per instance, draft 458 (median / mean / max) | cover-each K, draft 458 (median / max) | OFAT, draft 458 (median / max) |
|---|---|---|---|---|---|
| current `instructions.jsonc` | 1/1/1/2/2 | 1 / 1.7 / 4 | 1 / 1.2 / 4 | 1 / 4 | 1 / 7 |
| `today_superset` | 1/1/1/4/2 | 1 / 2.3 / 8 | 1 / 1.5 / 16 | 1 / 4 | 1 / 7 |
| `today_taint` | 1/1/1/3/2 | 1 / 2.0 / 6 | 1 / 1.4 / 9 | — | — |
| STT, ReCon (proposed) | 9/5/2/10/2 | 144 / 1499 / 5760 | 128 / 588 / 12800 | 8 / 10 | 16 / 34 |
| SPT (proposed) | 7/5/2/12/2 | 98 / 1153 / 4704 | 98 / 467 / 14112 | 7 / 12 | 14 / 36 |
| InvisiSpec (proposed) | 7/4/1/7/2 | 42 / 170 / 588 | 36 / 84 / 1764 | 6 / 7 | 11 / 23 |
| CleanupSpec (proposed) | 7/4/1/4/2 | 42 / 128 / 336 | 36 / 69 / 1296 | — | — |
| SpecLFB (proposed) | 7/1/1/4/2 | 42 / 86 / 336 | 36 / 55 / 1296 | — | — |
| DoM / Delay (proposed) | 7/4/1/6/2 | 42 / 156 / 504 | 36 / 79 / 1512 | 6 / 7 | 11 / 22 |
| STL (proposed) | 5/5/1/6/2 | 25 / 102 / 300 | 25 / 52 / 900 | 5 / 6 | 9 / 19 |

What this means for a 100k-instance testset (the gen_lit cap) with the STT table: one random draw per instance is 100k tests; cover-each is about 0.8-1M; full enumeration is about 13M at the median and 59M at the mean, which is not feasible at gem5 cost. Today, selection is a single random draw. A multi-draw is already possible with **no code change**: set `"interleave": {"enabled": true, "variants_per_instance": N, "num_chains_choices": [0]}`. `batch_generate` then re-seeds pass 2 for each variant (`batch_generate.py:100-102`), injects no chains (`:109-115`, `parsexml.py:1299-1305`), and writes `<stem>_v<k>`. Verified: 6 draws of `inst-047231` with `today_superset` gave 5 distinct combinations out of 8 possible. Downsides: draws repeat (instances with only 1 combination get N identical programs that differ only in register choice), and `_v<k>` already means "interleave variant" to downstream tools.

## Emitter-support gaps (all approval-gated `parsexml.py` changes)

- **G1 widths** (`load_zx8`, `load_zx16`, `load_32`, `load_sx32`, `store8`, `store16`, `store32`). Copy the `load` and `store` branches with a new mnemonic, using the LLVM operand modifiers `${n:b}`, `${n:w}`, `${n:k}` for the sub-register names; the probe compiled `movb %al`, `movw %cx`, `movl %r8d` correctly. Add each name to the probe_mem check (`parsexml.py:2063-2068`, which tests `in ("load", "store")`); otherwise `%probe_mem` is never allocated and the IR is invalid. Add size-aware read/write cases to `_stl_arch_values` (`:1131-1168`), plus the STL store retarget branch (`:2185-2215`).
- **G2 ALU ops** (`mov`, `addq`, `sub`, `xor`, `and`, `or`, `shl_imm`, `lea_scaled`, `mov_imm`). Each is a branch shaped like `bitnot`/`add`/`zsm` (`:2258-2332`), plus an `_stl_arch_values` case. Cheap.
- **G3 `store_imm`.** Route the name to the existing `store` branch (`elif concrete in ("store", "store_imm")`). Its `uses` leaves inreg0 without an SSA name, which already selects the `$0` immediate path. Also add it to the probe_mem check.
- **G4 `load_op_add`, `load_cmov`.** Put the setup instructions (zeroing the destination, setting flags from the reserved cond register, `_VPOOL_IDX_COND_REG` at `:1425`) *before* the pc label, so the label and therefore `xmit.addr` sit on the memory instruction. The probe compiled this layout.
- **G5 `prefetch`.** A new branch with no output. The uses filter (`:574`) already restricts it to loads whose output is unused. Before trusting `check_ld` verdicts, check on gem5 that the run logs an LSQ "Executing load" line for it and that the data-obtained gate is meaningful for a prefetch.
- **G6 branch vocabulary.** Pass 2.5 must stop forcing `br_bez`/`br_cond` (`:754-836`), or force a per-role list instead. `br_cmp` needs LLVM `callbr` (asm goto), because an IR `icmp`+`br` gets canonicalized to `testq/je`. `compile_annotate.find_branch_at_pc` already recognizes `jb` (`COND_JUMPS`, `:36-37`).
- **G7 `br_indirect`.** Needs a computed target, a BTB force for indirect targets in the gem5 hook (`--branch-ann-file` currently forces direction) and a `check_br` update. Large; defer.
- **G8 other_x marker.** Move the pc label from the `movq` prelude onto `imulq`/`idivq` (`:2321`, `:2376`) before any model makes `Otherxs` a transmitter.
- **G9 variant knob** (see V1). It would sit in `batch_generate.run_pipeline` / pass 2. Also record each record's chosen name in `ann.json`, so diagnostics can bucket hits by candidate.

## What was run (scratch only; nothing written into `testsets/` or `results/`)

- `today_superset`, `today_taint` and the current table went through the real passes: a harness mirroring `batch_generate.run_pipeline` with the unmodified `parsexml.py`. The 6 real XMLs used 8 seeds in each of the two branch modes (96 `.ll` per table, all compiled). The 458 draft XMLs used 4 seeds in `mispredict_not_taken` (1832 `.ll` per table, every 10th compiled). Result: 0 pass errors, 0 "unknown concrete_instruction", 0 clang failures, 0 missing pc markers.
- `batch_generate.py --instruction-tables proposed/today_superset.jsonc --interleave-config '{"enabled": true, "variants_per_instance": 6, "num_chains_choices": [0]}'` on 4 XMLs: 4/4 ok, and all 24 `.ll` compiled to x86-64 objects. The objects showed the other_x marker issue (`__litmus_..._pc1` lands on `movq %r12,%rax`, with `imulq` next).
- The scratch inline-asm probe assembled every proposed form: movzbq, movzwq, `movl ${0:k}`, movslq, the label-then-`addq` load-op, the label-then-`cmoveq` load (printed as `cmoveq`), prefetcht0, movb/movw/movl stores, movq-immediate store, and mov/add/sub/xor/and/or/shl/scaled-lea/mov-imm/zero-idiom.
- Not run: `compile_annotate.py` (needs `clang-15` and a GNU linker, which are not on this Mac), gem5, and the `stl_bypass` mode (no local STT_6_stl XML).

## Sources

- Local PDFs in `~/Documents/quail/sources/papers/`: `yu-2019-stt.pdf`, `choudhary-2021-spt.pdf`, `aimoniotis-2023-recon.pdf`, `yan-2018-invisispec.pdf`, `saileshwar-2019-cleanupspec.pdf`, `cheng-2024-speclfb.pdf`, `fu-2025-amulet.pdf`, `li-2022-unxpec.pdf`.
- Fetched this session (open author copies, read but not saved to `quail/sources`, per this task's file limits): NDA `https://homes.cs.washington.edu/~baris/public/nda.pdf`; DoM `https://www.sjalander.com/research/pdf/sjalander-isca2019.pdf`; Doppelganger `https://www.sjalander.com/research/pdf/sjalander-isca2023.pdf` (the published title is "Doppelganger Loads: A Safe, Complexity-Effective Optimization for Secure Speculation Schemes"). Anna may want to save these three to `quail/sources/papers/`.
- Code: `STAGE2_compilation/parsexml.py`, `batch_generate.py`, `compile_annotate.py`, `STAGE3_gem5/check_other.py`, `pipeline.py`, `testsetgen.py`, the three models' leakage functions, and the local gem5-recon source copy (O3 `secure_scheme` gating plus x86 microcode).

## Decisions for Anna

- [ ] DECIDE V1 (random vs enumerated vocabulary). Options: (a) keep one random draw per instance, as today; (b) N random draws via the zero-chain interleave knob, which needs no code but repeats draws and overloads `_v<k>`; (c) cover-each: K deterministic variants, where variant k picks candidate (k + offset) mod |valid| for each record, about 5-9× tests; (d) full enumeration capped at M; (e) one-factor-at-a-time variants around a hit, for triage only (about 9-17 per hit). (c)-(e) need a new knob, for example `concretize.vocab_mode: random|cover|enumerate|ofat` and `concretize.max_variants`, with `_c<k>` stems. **Recommendation:** use (a) for giant testsets, with each record's chosen name added to `ann.json` (it is already in the `.ll` comment, `parsexml.py:2128`), because at testset scale one random draw already covers every candidate many times. Use (e) when triaging a hit, since it isolates which form causes it, and (c) for focused per-defense campaigns.
- [ ] DECIDE V2 (which defenses get which table). (A) One shared superset for every defense: simplest, and since checkers only look at the transmitter, forms a defense never claims to protect are harmless. (B) Per-defense subsets, as tabulated above: spends the gem5 budget where each paper says it matters (SPT gets the untaint classes; the load-only defenses get load forms). **Recommendation:** (B), but generate the per-defense subsets from the one superset file, so there is a single source of truth and nothing drifts.
- [ ] DECIDE V3 (mul/div as never-transmitting ALU ops on the taint defenses). STT names "a multiplier" as a possible transmitter (p10 §7) and calls variable-latency arithmetic an explicit channel (p4); SPT counts variable-time arithmetic (p2). gem5-recon STT holds neither; `/work/stt` and `/work/gem5-spt` were not checked. Options: (a) zsm only, which is what `today_taint` does; (b) neither; (c) both. **Recommendation:** (a). It is the only non-invertible op SPT can test today, and if a build does hold mul, the extra delay can only hide a hit, never create one. First grep the `/work/stt` and `/work/gem5-spt` sources for IntMult/IntDiv gating (read-only).
- [ ] DECIDE V4 (order of the emitter work). **Recommendation:** G1 + G3 (widths and store_imm: small, help every defense), then G2 (SPT ALU classes), then G4 (load-op and cmov), G5 (prefetch, after a gem5 check), G6 (br_cmp), and G7 last. G8 matters only if Otherxs enters a leakage function.
- [ ] DECIDE V5 (semantics of the load-op). Zero the destination with an immediate first, so the output still depends only on memory as in Alloy's `ld`, or let `addq (mem),%d` also read the old `%d`, which adds a data edge Alloy never generated. **Recommendation:** zero it. SPT treats an immediate as public (p6 §6.5), so the zeroing adds no tainted edge.
- [ ] DECIDE V6 (zero idiom `xorq d,d`). SPT says it does not exploit this idiom (p6 §6.5). If a build does untaint it, that is correct behaviour (the output is constant) which the conservative model would still flag, so it would generate model-conservatism false positives. **Recommendation:** leave it out of the default tables; use it only as an explicit, labelled SPT probe.
- [x] DECIDED V7 2026-11-08 (Anna): RMW as a disjoint corpus (a separate testset of value-neutral RMW ld transmitters); the main tables are unchanged. Was: DECIDE V7 (RMW and `lock` RMW; **new evidence 2026-11-08:** CleanupSpec UV3 is reachable only through an RMW, see "RMW instructions: brief"; recommendation under review by the RMW agent). AMuLeT's InvisiSpec findings use `xorq %r,(mem)`, `orb %al,(mem)` and `lock andl`. One such instruction is load + ALU + store, which no single Alloy kind describes. Options: model it (a new kind, or an ld+str pair that shares an address) or leave it out. **Recommendation:** leave it out for now and note it as a known coverage gap relative to AMuLeT.
- [ ] DECIDE V8 (interleave chain vocabulary). `_build_chain` hardcodes bitnot/add/load/store (`parsexml.py:307-331`). Should injected chain steps draw from the same per-defense table? **Recommendation:** yes, once the tables grow, but as a separate change.
- [ ] DECIDE V9 (NDA and Doppelganger). **Correction (simspect-c8, 2026-11-07):** both DO have builds. NDA is `--scheme 1` on `/work/gem5-recon-modded` (enum named `Delay` at `cpu.hh:455-461`; the load reaches the cache and its writeback is held, `lsq_unit.cc:194-211`; Pavlos's email `documentation/docs/Files/email.txt` calls it NDA). Doppelganger is `--address_prediction` on the same binary (`configs/common/Options.py:430`, `Simulation.py:475`; simple memory, no `--ruby`). See `wiki/findings/audits/2026-11-07/HOOK_AUDIT.md`. The agent's original text follows: there is no build for either. **Recommendation:** no tables until a build exists; treat Delay (scheme 1) as "NDA-like" only after confirming in the gem5-recon source that it implements permissive propagation.
