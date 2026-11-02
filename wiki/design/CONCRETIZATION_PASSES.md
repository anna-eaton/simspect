# Stage 2 concretization passes (`parsexml.py`): exact order, lines, and what each does

*Living doc, overwrite-in-place. Written 2026-11-02 from a read of the working tree, for the paper's concretization figure. Line numbers are working-tree `STAGE2_compilation/parsexml.py` unless another file is named. `bg:` means `STAGE2_compilation/batch_generate.py`. `parsexml.py` has uncommitted changes; §6 says why they don't affect the pass list.*

## Summary

Stage 2's `llvm` phase turns one Alloy XML instance into `inst-*.ll` plus a bare `inst-*.ann.json`. The pass order is set in one place, `batch_generate.py:run_pipeline` (bg:79-125). `pipeline.py:phase_llvm` runs it as a subprocess (pipeline.py:179-197), and `testsetgen.py` reuses `phase_llvm` (testsetgen.py:38, 165). The `__main__` block in `parsexml.py` (2665-2668) only runs pass1 and is not the driver. The order is: parse, then pass1 (once per XML and mode), then for each variant: pass2, pass2_5, pass2_6 (`stl_bypass` mode only), pass_interleave (always called, a no-op unless enabled), pass3, pass4, pass5 (writes `.ll`), and emit_branch_annotations (writes `.ann.json`). The `asm` phase then runs `compile_annotate.py`, which compiles the `.ll` and replaces the annotation's PC keys with absolute x86 addresses. **No Stage 2 code writes timing directives.** Per-branch `resolve_stall_cycles` are added at Stage 3 by `pipeline._inject_stalls`, and only on sweep runs. **For the figure:** instruction choice (pass2) and the speculation-primitive passes (pass2_5, pass2_6) run *before* interleave. Physical registers, for both the Alloy-reserved state and the interleaved chains' free pool, are assigned *after* interleave, in pass3.

## 1. The real call path

- `python3 pipeline.py llvm` calls `phase_llvm` (pipeline.py:138), which runs `batch_generate.py <tmp xml dir> --out <llvm_dir> --kind --instruction-tables <path> [--mode M] [--interleave-config JSON]` (pipeline.py:179-197). When `speculation.branch_modes` is set, `main` calls `phase_llvm` once per mode (pipeline.py:1240-1282, call at 1274). `testsetgen.py` imports and calls the same `phase_llvm` once per mode (testsetgen.py:38, 165).
- `batch_generate.py:main` (bg:200) calls `process_folder` (bg:138). That loops over XML files and then over modes (bg:170-174), calling `run_pipeline(...)` for each (bg:183). `--kind` does nothing; it is kept so old call sites still work (bg:35-36).
- `run_pipeline` (bg:79-125) is the only code that puts the passes in order. `batch_generate.py` is identical to HEAD.

```
bg:94       inst = parse_alloy_xml(xml_text)
bg:95       r1   = pass1(inst)                         # once per (XML, mode)
bg:100      for v in range(n_variants):                # n_variants = variants_per_instance if interleave.enabled else 1  (bg:90-92)
bg:101-102      random.seed(zlib.crc32(f"{stem}_v{v}"))
bg:104          r2   = pass2(r1)
bg:105          r25  = pass2_5(r2, branch_mode=mode)
bg:106-107      if mode == "stl_bypass": r25 = pass2_6(r25)
bg:108          rng  = random.Random(vseed ^ 0xABCD_1234)
bg:109-117      r_il = pass_il(r25, icfg if enabled else None, rng)   # per-variant num_chains override at bg:109-115
bg:118          r3   = pass3(r_il)
bg:119          r4   = pass4(r3)
bg:124          pass5(r4, func_name=vstem, out_path=<vstem>.ll)
bg:125          emit_ann(r4, out_path=<vstem>.ann.json)
```

## 2. Passes in execution order

0. **`parse_alloy_xml`** (def 20, called bg:94, always). This is not a concretization pass. It parses the XML into an `AlloyInstance` with `sig_atoms` (sig label to atom set) and `fields` (field label to tuples) (20-41).
1. **`pass1_specify_state_a`** (def 347, called bg:95 once per XML and mode, before the variant loop; always). It topologically sorts the `Instruction` atoms by `spo` and uses that position as the PC (358-364, 404). For each instruction it records the kind token from the `kind` field (356, 405), the Alloy flags `resolved`, `committed`, `must_uncommitted` and `xm` (376-382, 442-454), and five slot roles (`inreg` x2, `inaddr`, `inmem`, `outreg`, `outmem`). Each slot is either *specified*, with its `opstate` atom stored as `physical`, or *unspecified* (396-440, helper 134-163). It also collects every `Reg_s`/`Mem_s` atom used into `resource_usage` (418-425, 466-473). The header comment calls this "save them to a reserved list" (340-341). It chooses no physical register.
2. **`pass2_specify_instructions`** (def 535, called bg:104 per variant; always). It maps each kind to an instruction-table category (`_KIND_TO_CATEGORY`, loaded from `instruction_tables/instructions.jsonc`, 493-532). It keeps the candidates whose `uses` set covers every specified slot, falls back to all candidates if none fit, and picks one with `random.choice` (561-588). It adds `concrete_instruction`, `llvm_op` and `candidates`. The current table maps ld to load; str to store; br to br_uncond, br_cond or br_bez; other_n to bitnot or add; other_x to zsm or div. The docstring (549-551) and the comment at 528-531 say "fewest uses wins", but the code picks at random (581-582).
3. **`pass2_5_specify_branches`** (def 639, called bg:105; always, in every mode). This pass concretizes the *branch* speculation primitives. It raises unless the mode is `mispredict_not_taken`, `mispredict_taken` or `stl_bypass` (707-708). In `stl_bypass` it rejects any unresolved non-xmit branch (709-719). The per-branch rules are:
    - The xmit branch always becomes `br_bez`, with BTB-forced fall-through and `mode: "mispredict_not_taken"`. This ignores both the Alloy resolved flag and the run mode (754-779).
    - The xmit branch gets a synthetic `_xm_fallthrough_nop` only when it is the last instruction (768-769, 880-904).
    - Every other branch is forced to `br_cond` (789-794).
    - A resolved branch gets `mode: "correctly_not_taken"` (796-819).
    - An unresolved branch gets `mispredict_not_taken` (838-856) or `mispredict_taken` (858-876), depending on the run mode.

    Each branch record gets `branch_annotations` = {mode, condition_value, taken_target, fallthrough_target, btb_prediction, btb_predicted_pc}. The result gets `branch_mode` and `needs_end_block` (920-925).
4. **`pass2_6_specify_stl`** (def 981, called bg:107). **Conditional:** it runs only when the mode is `stl_bypass` (gate at bg:106-107; the docstring at 704-705 also says this). It concretizes the *store-to-load* speculation primitive, which its docstring calls "a false-negative alias prediction" (986-990). For each unresolved, non-synthetic store S, it finds the first uncommitted load that reads S's `Mem_s` before another store writes it and tags it `bypass_load`. It tags every later such load `alias_load` (a working-tree change), and all of them share one `pair` id (1015-1034). The tags live on the records, not on PCs, because pass_interleave renumbers PCs (1002-1003). It raises, so the test is skipped, if there is no unresolved store, or a store has no outmem or no aliasing load (1019-1020, 1028-1029, 1036-1037).
5. **`pass_interleave`** (def 1255, called bg:115 or bg:117). **Conditional:** it is always called, but it returns its input unchanged (plus empty `fr_reg_pool` and `fr_mem_pool`) unless `interleave.enabled` is set (1282-1287). It also does nothing when the variant's `num_chains` is 0 (1299-1305); bg:111-112 sets that for variant 0 when `variant_zero_no_chain` is on. When active:
    - It builds 1–2 chains of synthetic steps (`other_n`, `ld` or `str`; length set by `chain.min_length`/`max_length`, defaults 2–4). Each step's concrete instruction is hard-coded in `_build_chain` (bitnot, add, load or store; 299-332), so pass2 never sees these steps.
    - It creates free-pool state atoms `Reg_s$fr*` and `Mem_s$fr*` (1307-1308). It pins only each step's bridge input and its output to them; the other inputs stay floating (281-332).
    - It inserts the steps at random positions in the uncommitted suffix (1319-1358) and renumbers every PC (1360-1362).
    - It rewrites each branch's `btb_predicted_pc` and `bb_*` targets to match the new PCs (1374-1389).

    Chain steps carry `synthetic: True` (204). Its docstring calls it an "Optional pass between pass2.5 and pass3" (1261).
6. **`pass3_assign_operands`** (def 1444, called bg:118; always). This pass assigns physical locations to all state.
    - **Reserved Alloy registers.** The locked `Reg_s` atoms from pass1's `resource_usage` take the front of `X86_64_CALLER_SAVED` (rax, rcx, rdx, rsi, rdi, r8–r11, then r12–r15; 1408-1416, 1494-1508).
    - **Reserved codegen registers.** The next three registers are kept for code generation: scratch, the branch-condition register and the probe base (1418-1427, 1513-1517).
    - **Chain registers.** `Reg_s$fr*` atoms map onto the head of the remaining `free_pool` (1534-1537). Alloy-unspecified outregs avoid that region (1538-1543, 1583-1584).
    - **Other register slots.** Unspecified slots that the instruction uses draw randomly from `free_pool` (1577-1587). Unused slots get `None` (1588-1589).
    - **Memory.** Locked `Mem_s` atoms get fixed 8-byte offsets (1519-1522). `Mem_s$fr*` atoms come right after them (1546-1548). Each unspecified memory slot that is used gets a fresh offset (1600-1602).

    It outputs `locked_registers`, `virtual_reg_pool`, `memory_offsets`, `alloca_total_slots` and `alloca_total_bytes`, plus `condition_assigned` on branches (1611-1633).
7. **`pass4_ssa`** (def 1705, called bg:119; always). It gives every used register slot an SSA name `{reg}_{n}`, resolving reads before writes within each instruction (1763-1816). It records registers read before their first write in `ssa_init` (1774-1779, 1836) and sets `condition_ssa_forced` on branches (1818-1822). It passes pass3's pools and offsets through unchanged (1826-1837).
8. **`pass5_emit_llvm`** (def 1934, called bg:124; always). It writes `<vstem>.ll`, a single function `@<vstem>() -> i64`:
    - **Prologue.** A zero-initialised `[N x i64]` alloca `%mem_base` (2071-2076); a 256-slot `%probe_mem` when any load or store uses a specified inaddr (2063-2085); inline-asm zero-init of the `ssa_init` registers (2087-2089); and an `mfence` barrier (2096).
    - **Labels.** Each instruction is an `asm sideeffect` that carries the global label `__litmus_<stem>_pc<N>`. The lc and fnc instructions picked by `commit_boundary` also carry `__litmus_<stem>_last_committed` and `__litmus_<stem>_first_noncommitted` (2105-2140).
    - **Branch primitives.** The xmit becomes `br_bez` (2387-2431). Other branches become `br_cond`, with an `ftbypass_<pc>` trampoline for `mispredict_taken` and for resolved branches whose two edges collapse (2438-2521).
    - **STL primitive.** Each STL store is re-addressed to its bypass load's runtime address via `_stl_store_retargets` (2098-2103, 2185-2215; helper 1172-1222).
    - **Other.** Non-xmit `div` divisors are forced nonzero (2334-2349). An `end_block: ret i64 0` is appended when needed (2540-2547).

    The docstring at 1970 says "Resolved branches are emitted as a comment", which is out of date: they are real `br_cond`s (2445-2521).
9. **`emit_branch_annotations`** (def 2565, called bg:125; always). It writes the bare `<vstem>.ann.json` (keys in §4). It is not a transform: it returns the annotation list and leaves the program dict alone. Its docstring says the list has "one per unresolved branch" (2582). In fact it emits an entry for every branch that has `branch_annotations`, including resolved `correctly_not_taken` ones (2598-2607).

**Helper, not a pass: `commit_boundary`** (def 1902). It is called from pass5 (2106) and from emit_branch_annotations (2622). It returns the last committed record and the first must-be-uncommitted record, skipping `synthetic` records (1919-1927). Because both callers use it, the `.ll` labels and the annotation boundary always agree (1914-1916; [`COMMIT_BOUNDARY.md`](COMMIT_BOUNDARY.md) §1).

**After the llvm phase (the `asm` phase, still Stage 2): `compile_annotate.py`.** `pipeline.py:phase_asm` runs it for each `.ll` (pipeline.py:251-262), and so does the streaming path (pipeline.py:1011-1015). It compiles with `clang-15 -O2` (compile_annotate.py:96-104), links a static binary (52-83), reads the `__litmus_*` labels with `nm` (108-163), and writes the resolved annotation to `<mode>/ann/` (357-362). It is not part of `parsexml.py`.

## 3. Hand-drawn figure items mapped to passes

| Figure item | What does it in the code | Agrees with the code order? |
|---|---|---|
| "concretize state, reserve regs" | Two passes. **pass1** (347; bg:95) extracts each operand's `Reg_s`/`Mem_s` state atom and builds the `resource_usage` "reserved list" (340-341, 418-425, 466-473). **pass3** (1444; bg:118) does the actual reservation: locked `Reg_s` atoms take the front registers (1505-1508), 3 more registers are kept for codegen (1418-1427, 1517), and locked `Mem_s` atoms get fixed offsets (1519-1522). | Partly. The state extraction is first (pass1), but physical registers are reserved in pass3, which runs *after* interleave. |
| "interleave" | **pass_interleave** (1255; bg:115/117). Always called; does nothing unless `interleave.enabled` is set (1282-1287) and `num_chains` > 0 (1299-1305). | **No.** In code it runs after pass2, pass2_5 and pass2_6 (bg:104-117), and it patches pass2_5's branch annotations to the new PCs (1374-1389). |
| "state for the interleaved chains" | Not a separate pass. **pass_interleave** creates the free-pool atoms `Reg_s$fr*`/`Mem_s$fr*` and pins chain-step slots to them (1307-1308, 180-182, 281-332). **pass3** maps them to physical registers (1534-1537) and memory slots (1546-1548), and keeps Alloy outregs out of the chain registers (1538-1543, 1583-1584). | Yes, it comes after interleave. In code it happens inside pass_interleave plus pass3. |
| "concretize instructions" | **pass2_specify_instructions** (535; bg:104): picks at random among table candidates (561-588). Chain-step instructions are hard-coded in `_build_chain` (299-332), not chosen by pass2. pass2_5 then overrides branch instructions (xmit to `br_bez`, 754-759; others to `br_cond`, 789-794). | **No.** pass2 runs *before* interleave (bg:104 vs bg:115/117). |
| "concretize S.P." (speculation primitive, see §5) | **pass2_5_specify_branches** (639; bg:105) for the branch primitives. **pass2_6_specify_stl** (981; bg:107, `stl_bypass` only) for the store-to-load primitive. Both are realized in code by pass5 (branches 2387-2533; STL store retarget 2098-2103, 2185-2215). | **No.** Both run *before* interleave. pass2_6 tags records rather than PCs precisely because interleave renumbers later (1002-1003). |
| "concretize resolution + timing annotations" | **Resolution:** pass2_5 turns the Alloy `resolved` flag into each branch's `mode` (`correctly_not_taken` vs `mispredict_*`; the xmit is always `mispredict_not_taken`, 771-778), and emit_branch_annotations writes it out (2598-2607). **Timing: not in Stage 2.** `resolve_stall_cycles` is added at Stage 3 by `pipeline._inject_stalls` (pipeline.py:404-428), only when `sweep.enabled` (pipeline.py:1068-1073, 915). The fnc commit stall and the STL store-address stall come from `gem5.*` config keys (pipeline.py:597-613), keyed to the annotation's `commit_boundary.first_noncommitted` and `stl_annotations` (gem5_common.py:398-408, 1106). | Resolution: yes, but it is set in pass2_5, before interleave. Timing: only if the figure covers Stage 3. |
| "PC-indexed annotations: labels, speculation directives, timing directives" | **Labels:** pass5 emits the `__litmus_<stem>_pc<N>`, `_last_committed`, `_first_noncommitted` and `_ftbypass<pc>` global asm labels (2129-2140, 2502, 2514). **Speculation directives:** emit_branch_annotations writes `annotations[]` and `stl_annotations[]`, keyed by post-interleave Alloy PC (2565-2662). compile_annotate.py turns the PC keys into absolute addresses using those labels (compile_annotate.py:137-163, 223-312). **Timing directives:** Stage 3, as in the row above. | Yes, as the last output. "Timing directives" are the exception: Stage 2 never writes them. |

## 4. `.ann.json` contents

### 4.1 Bare annotation, written by `emit_branch_annotations` (2628-2660) to `<mode>/llvm/<vstem>.ann.json` (bg:123, 125)

| Key | Content | Lines |
|---|---|---|
| `branch_mode` | The run mode, taken from pass2_5's result (923). | 2632 |
| `annotations[]` | One entry per branch that has `branch_annotations` (resolved ones included): `branch_pc`, `branch_atom`, `btb_forced_target_pc`, `mode` (`mispredict_not_taken`, `mispredict_taken` or `correctly_not_taken`). | 2598-2607, 2633 |
| `xmit` | `{pc, kind, atom}` of the first `xm` record. `kind` is pass1's kind token; the checker is chosen from it (pipeline.py:296-300). | 2611-2619, 2635-2636 |
| `commit_boundary` | `{last_committed: {pc, atom}, first_noncommitted: {pc, atom}}`, from `commit_boundary`. | 2621-2626, 2637-2643 |
| `stl_annotations[]` | `stl_bypass` only. One entry per aliasing load: `{store_pc, load_pc, role, mem_atom, mode: "stl_bypass"}`. `role` is `"bypass"` for the first load and `"alias"` for later ones, and an alias load is kept only if its runtime address equals the store's (`_stl_alias_load_matches`, 1225-1248). `role` and the alias entries are uncommitted working-tree changes. | 2644-2657 |

Every PC in this file is a post-interleave instruction index (pass_interleave renumbers PCs at 1360-1362). It is the same `N` as in the `__litmus_<stem>_pc<N>` labels, which is why the file is PC-indexed.

### 4.2 Resolved annotation, rewritten by `compile_annotate.py:update_annotations` (223-312) into `<mode>/ann/`

It adds `func_base_addr[_hex]` (239-240). For each annotation it adds `branch_addr[_hex]`, the first conditional jump at or after the pc label (255-259, `find_branch_at_pc` 206-220), and `btb_forced_target_addr[_hex]` (263-267), and drops `branch_atom` (248). It adds `xmit.addr[_hex]`, which for `br_x` is the jcc (270-281); `stl_annotations[].store_addr` / `load_addr[_hex]` (286-291); and `commit_boundary.*.addr[_hex]`, moved to the jcc address when the boundary instruction is a branch (296-310). Every address is absolute (227-233).

### 4.3 Added at Stage 3, not by Stage 2

- `resolve_stall_cycles` on each annotation, from `pipeline._inject_stalls` (pipeline.py:404-428): 0 for the xmit; the swept grid value for `correctly_not_taken`; `sweep.unresolved_stall_cycles` for `mispredict_*`. This happens only on the sweep path (`phase_gem5` at pipeline.py:1068-1073; streaming at pipeline.py:915, 937), via `_materialise_grid_run` (pipeline.py:471-495). With `sweep.enabled: false` the key is never written, and `gem5_common` reads it with a default of 0 (gem5_common.py:877). `parsexml.py` mentions `resolve_stall_cycles` only in comments (801-802, 2398, 2451-2452).
- The `branch_pc_addr[_hex]` key alias. On builds with the resolve hooks only, also `mode: "simspect_force"`, `orig_mode` and a rewritten `btb_forced_target_addr`; this part is uncommitted working-tree code. Both come from `gem5_common._branch_ann_for_se` (gem5_common.py:317-364), which writes the copy passed to gem5 as `--branch-ann-file` (gem5_common.py:392-396).
- Timing set in the config, not in the annotation: `gem5.fnc_commit_stall_cycles` becomes `--fnc-commit-stall-pc` / `--fnc-commit-stall-cycles` at the annotation's fnc (pipeline.py:611-613; gem5_common.py:406-408, 1106). `gem5.stl_store_addr_stall_cycles` becomes `--stl-store-stall-cycles`, with the annotation passed as `--stl-ann-file` (pipeline.py:597-606; gem5_common.py:398-401).

## 5. "S.P." most likely means "speculation primitive"

No file in the repo contains the literal string "S.P.", so this is an inference. Everything below points the same way, and no other expansion matches a concretization step:

- `parsexml.py:704-705`: in `stl_bypass` mode, "The speculation primitive is annotated afterwards by pass2_6_specify_stl."
- `parsexml.py:986-990`: "The speculation primitive is a false-negative alias prediction ..."
- `paper_figures/spec_primitives/sptable_v2.tex:27-28`: the caption reads "Every speculation-primitive instance we concretize", and the label is `tab:sptable`. Anna's own short form for speculation primitive is therefore "sp".
- [`SPEC_PRIMITIVE_INSTANCES.md`](SPEC_PRIMITIVE_INSTANCES.md) line 1 places that table in the paper's §Concretization. Line 43, the suggested prose, says "Table~\ref{tab:sptable} lists every speculation primitive we instantiate."
- `PAPER_PLAN.md:95`: §5 Concretization covers "speculation-primitive instrumentation (Table 1, Fig. 6)".
- `documentation/simspect-master.md:7` gives the definition: "Speculation primitives: instructions that initiate speculative executions, e.g., a conditional branch".
- `old/README.md:76`: the 2025 feature-division table lists "speculation primitives - set state for speculation primitives" under the enumeration (concretization) column.

The nearest alternative, the "speculative protection set" from the root `CLAUDE.md`, is a model-side concept (`hardware_protection_policy` in the `.als`) that no Stage 2 pass handles.

## 6. Uncommitted working-tree changes to `parsexml.py`

`git diff --stat` shows 54 lines added and 11 removed, all in the STL code:

- pass2_6 now also tags `alias_load` records (1015-1034).
- `_stl_pairs` collects `alias_load_pcs` (1044-1059).
- `_stl_store_retargets` also returns `addr` (1220-1221).
- `_stl_alias_load_matches` is new (1225-1248).
- emit_branch_annotations emits `role` and the alias entries (2644-2657).

**No pass is added, removed, renamed or reordered.** The order lives in `batch_generate.py`, which is identical to HEAD. Line numbers: definitions up to pass2_6 (981) are the same in HEAD and the working tree. From pass_interleave on, the working tree is 38 lines later. HEAD has `_stl_store_retargets` 1161, pass_interleave 1217, pass3 1406, pass4 1667, commit_boundary 1864, pass5 1896 and emit_branch_annotations 2527.

## 7. Docs that describe the passes, and whether they're stale

| Doc | Last commit | Stale relative to the code? |
|---|---|---|
| [`METHODS_CONCRETIZATION.md`](METHODS_CONCRETIZATION.md) §2 | 2026-10-20 | **Partly stale.** The order is right for the passes it lists, but it omits pass2_6 and commit_boundary. Most line numbers are old (529/633/950/1139/1400/1597/2195 vs 535/639/1255/1444/1705/1934/2565; only 347 matches). §2.2 puts the idivq guard in pass2; it is in pass5 (2334-2349). §2.6 says pass4 builds the virtual pool and alloca offsets; pass3 does (1513-1522, 1618-1619). §2.8 says the annotation carries resolve-stall cycles; those are added at Stage 3 (§4.3). |
| `STAGE2_compilation/SimSpect Concretization Passes.md` | 2026-04-20 | **Stale.** Its pass list is 1, 2, 2.5, 3, 4, 5 plus emit, with no pass_interleave and no pass2_6. It doesn't cover interleave, STL, `correctly_not_taken`, r12–r15 or `resolve_stall`, and it uses the old path `alloy/parsexml.py`. |
| `STAGE2_compilation/simspectmaster.md` §2.1 | 2026-04-12 | **Stale.** Same list without emit_branch_annotations; path `alloy/parsexml.py`. |
| `documentation/docs/concretization.md` | 2026-10-26 | **Stale.** Same 1–5 list. It does have PC markers, `commit_boundary` and `br_bez`, but no interleave or STL, and it still says resolved branches "pass through unchanged" (line 133) and are emitted as comments (line 512). |
| `documentation/concretization old.md`, `bugsynth/STAGE2_compilation/SimSpect Concretization Passes.md` | 2026-10-26, 2026-10-20 | **Stale** copies of the April doc. `bugsynth/` also has its own older `parsexml.py`. |
| [`SPEC_PRIMITIVE_INSTANCES.md`](SPEC_PRIMITIVE_INSTANCES.md) | 2026-10-29 | Content is current; the line numbers are not. It cites `parsexml.py:772` for (b) (`correctly_not_taken`, now 796-819), `:834` for (c) (`mispredict_taken`, now 858-876), and `:716` for (g) (the xmit override, now 754-779). |
| [`DESIGN.md`](DESIGN.md), "Where the code depends on this invariant" | 2026-10-20 | **Stale.** It describes the NOP being injected "when the next list entry is also a branch", with resolved branches skipping at `:737`. Now the xmit override runs first and `continue`s (754-779), and the NOP is queued only when the xmit is last (768-769, 906-918). |
| [`COMMIT_BOUNDARY.md`](COMMIT_BOUNDARY.md) | 2026-10-30 (+ working-tree edits) | Current. |
| [`STL_SPECULATION.md`](STL_SPECULATION.md) "Concretization" | 2026-10-29 (+ working-tree edits) | Current about pass2_6 and the alias-load fix (line 119). Its key list at line 70 (`{store_pc, load_pc, mem_atom, mode}`) lacks the new `role` key. |
| Root `CLAUDE.md` "Chain interleaving" | — | Current about pass_interleave and pass3. It has no full pass list. |

## 8. Open / uncertain

- **"S.P."** is an inference (§5). No document spells out the abbreviation.
- **"reserve regs" has two possible meanings in the code**, and both happen in pass3: (a) the front registers reserved for Alloy-locked `Reg_s` state (1505-1508), and (b) the 3 registers reserved for codegen (1418-1427). pass1 only builds the list. I can't tell which one the figure means.
- **DECIDE (figure order):** the hand-drawn order (state, interleave, chain state, instructions, S.P., resolution/timing) is not the execution order (§3). Options: (a) redraw in code order: state extraction (pass1), instructions (pass2), S.P. + resolution (pass2_5/2_6), interleave + chain atoms (pass_interleave), physical registers/offsets with the reserved registers (pass3), SSA (pass4), emit + labels (pass5), annotations (emit_branch_annotations, then compile_annotate); (b) keep a conceptual order and caption it as conceptual, not execution order. *Recommendation:* (a). In the code, interleave patches pass2_5's annotations and pass2_6 tags records because interleave renumbers later, so drawing interleave first describes a pipeline that doesn't exist.
- **DECIDE (timing directives):** Stage 2 never writes timing. `resolve_stall_cycles` comes from Stage 3 and only exists on sweep runs; the fnc and STL store stalls are config flags. Options: (a) move "timing directives" to the Stage 3 / harness box; (b) keep it in concretization and say it is "attached at run time". *Recommendation:* (a), or (b) with that caption.
- Whether the figure should show pass4 (SSA) and pass5 (emit) at all. The hand-drawn list has no item for either, and they are real passes.
- I did not read the gem5 `se.py` annotation loaders. What gem5 does when `resolve_stall_cycles` is absent is established here only on the Python side (gem5_common.py:877 defaults it to 0).
- Dead code, not a doubt: in pass2_5, the `is_xm` checks at 834-836, 844-846 and 864-866 can never be true, because every xmit branch already `continue`d at 779.
