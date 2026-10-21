All passes live in `alloy/parsexml.py`. Each pass takes the output dict of the previous pass and returns an enriched dict. Passes can optionally write a human-readable `.ir` text file (`write_out=True`, `out_path=...`). The full pipeline in order:

```
Alloy XML
→ Pass 1   pass1_specify_state_a
→ Pass 2   pass2_specify_instructions
→ Pass 2.5 pass2_5_specify_branches
→ Pass 3   pass3_assign_operands
→ Pass 4   pass4_ssa
→ Pass 5   pass5_emit_llvm            → LLVM IR text (.ll)
             emit_branch_annotations  → BTB force annotations (.json)
```
---
### 2.1.1 Pass 1 — Parse and extract abstract state
**Function:** `pass1_specify_state_a(inst, out_path, write_out)`

**Input:** An `AlloyInstance` produced by `parse_alloy_xml(xml_text)`, which parses raw Alloy XML. The XML contains the Alloy model's solution: typed instruction atoms (`Load`, `Store`, `Branchn`, `Branchx`, `Othern`, `Otherx`), state atoms (`Reg_s$*`, `Mem_s$*`), operand atoms (`Inreg$*`, `Outreg$*`, `Inmem$*`, `Outmem$*`), and relations between them (`spo`, `inreg`, `outreg`, `inmem`, `outmem`, `inaddr`, `opstate`, `isresolved`, `iscommitted`).

**What it does:**
1. Collects all instruction atoms across the six typed sigs.
2. Topologically sorts them by the `spo` (speculative program order) relation to produce a linear execution order.
3. For each instruction, maps its operand atoms (e.g. `Inreg$0`) to their physical state via the `opstate` relation. A physical state is either a `Reg_s$*` atom (register location) or a `Mem_s$*` atom (memory location). This distinction is what makes two operands "the same physical location."
4. Populates slot records for each operand role. Every instruction has the same fixed set of roles: `inreg` (2 slots: `inreg0`, `inreg1`), `inaddr` (1 slot), `inmem` (1 slot), `outreg` (1 slot), `outmem` (1 slot). A slot is **specified** if the Alloy model assigned it a physical state, and **nonspecified** otherwise.
5. Collects the set of unique physical register states (`Reg_s$*`) and memory states (`Mem_s$*`) used across all instructions.

**Output dict:**
```python
{
"instructions": [
{
"pc": int, # position in topological order
"instruction": str, # atom name, e.g. "Load$0"
"kind": str, # "ld" | "str" | "br_n" | "br_x" | "other_n" | "other_x"
"resolved": bool, # from isresolved relation
"committed": bool, # from iscommitted relation
"slots": {
"inreg": [ {slot, specified, operand_atom, physical}, ... ], # 2 entries
"inaddr": [ {slot, specified, operand_atom, physical} ], # 1 entry
"inmem": [ {slot, specified, operand_atom, physical} ], # 1 entry
"outreg": [ {slot, specified, operand_atom, physical} ], # 1 entry
"outmem": [ {slot, specified, operand_atom, physical} ] # 1 entry
}
}, ...
],
"resource_usage": {
"register_count": int, # number of unique Reg_s$* atoms
"memory_count": int, # number of unique Mem_s$* atoms
"registers": [ "Reg_s$0", ... ], # sorted list
"memory": [ "Mem_s$0", ... ] # sorted list
}
}
```

Each slot record: `{"slot": str, "specified": bool, "operand_atom": str|None, "physical": str|None}`. `physical` is the `Reg_s$*` or `Mem_s$*` atom name, or `None` if nonspecified.

**Key design choices:**
- Physical identity is keyed by `opstate`, not by operand atom. Two different operand atoms that share the same `Reg_s$*` via `opstate` represent the same physical register location. This is what allows later passes to enforce that they map to the same physical register.
- `resolved` and `committed` flags are preserved through all subsequent passes — they are the primary microarchitectural metadata the pipeline is designed around.

---
### 2.1.2 Pass 2 — Specify concrete instruction types

**Function:** `pass2_specify_instructions(pass1_result, instruction_table, out_path, write_out)`
**Input:** Pass 1 dict.
**What it does:**
Assigns a concrete LLVM-level instruction type to each abstract instruction atom. Uses a static `INSTRUCTION_TABLE` that maps four instruction categories to one or two concrete candidates each. Each candidate declares which operand slots it actually uses (`"uses"` set), using the slot names from pass 1.

The instruction table (defined in `parsexml.py`):
| Category | Concrete name | `llvm_op`            | `uses` (slot names)        |
| -------- | ------------- | -------------------- | -------------------------- |
| `ld`     | `load`        | `load volatile i64`  | `{inaddr, inmem, outreg}`  |
| `str`    | `store`       | `store volatile i64` | `{inreg0, inaddr, outmem}` |
| `br`     | `br_uncond`   | `br label`           | `{}`                       |
| `br`     | `br_cond`     | `br i1`              | `{inreg0}`                 |
| `other`  | `bitnot`      | `xor i64`            | `{inreg0, outreg}`         |
| `other`  | `add`         | `add i64`            | `{inreg0, inreg1, outreg}` |

Kind tokens are normalized to categories first: `br_n`/`br_x` → `br`, `other_n`/`other_x` → `other`.
NO LONGER TRUE< THEY ARE SPLIT UP

**Filtering rule:** For a given abstract instruction, collect the set of slot names that are already specified (have a physical state from Alloy). Filter the category's candidates to those whose `uses` set is a **superset** of the specified slots — i.e. every slot the Alloy model has pinned must be consumed by the chosen instruction. Among valid candidates, choose **randomly** (using `random.choice`). If no candidate covers all specified slots (model/table inconsistency), fall back to all candidates.

Example: `Otherx$0` with `inreg0` specified → `bitnot` (uses `{inreg0, outreg}`) and `add` (uses `{inreg0, inreg1, outreg}`) are both valid; one is chosen at random. If `inreg1` were also specified, only `add` would be valid.

**Output dict:** Same structure as pass 1, with three fields added to each instruction record:

```python
{
"concrete_instruction": str, # e.g. "load", "bitnot", "br_cond"
"llvm_op": str, # e.g. "load volatile i64", "xor i64"
"candidates": list, # all valid concrete names for this instruction
# ...all pass-1 fields preserved unchanged
}
```

**Key design choices:**

- The `uses` set controls which operand slots will actually appear in the final emitted instruction. Slots not in `uses` are never assigned real values and are marked `None` in later passes. This prevents wasted register/memory allocations.

- Randomness is at the instruction level. Re-running the pipeline with a different random seed produces different concrete instruction assignments where there is choice.

---

### 2.1.3 Pass 2.5 — Annotate branch mispredictions
I SIMPLIFIED ONLY WITH THE ONE VERSION

**Function:** `pass2_5_specify_branches(pass2_result, branch_mode, out_path, write_out)`

**Input:** Pass 2 dict.

**What it does:**
Annotates unresolved branch instructions (`resolved=False` and `kind` in `{"br_n", "br_x"}`) with misprediction metadata. Resolved branches pass through unchanged. All non-branch instructions pass through unchanged.

Currently only one mode is active (`branch_mode="mispredict_not_taken"`). A second mode (`mispredict_taken`) is stubbed and raises `NotImplementedError`.

**Mode: `mispredict_not_taken` (default)**
The branch IS architecturally taken (condition resolves to `True`), but the branch target buffer (BTB) predicts fall-through (not taken). The CPU therefore speculatively executes the instructions that follow the branch in program order (the fall-through path), then squashes that work when the branch resolves as taken.
- `condition_value = True` — the branch condition evaluates to true (branch taken)
- `taken_target = "end_block"` — the architectural destination label (a block appended after all instructions)
- `fallthrough_target = "bb_{pc+1}"` — the speculative execution path (next sequential instruction's block label); `"end_block"` if the branch is the last instruction
- `btb_prediction = "fall_through"` — what the BTB predicts
- `btb_predicted_pc = pc + 1` — **this is the simulator override point**: the PC the BTB thinks comes next. Overwrite this value in the simulator to change the BTB's prediction.

If pass 2 assigned `br_uncond` to an unresolved branch (because no operands were specified), it is upgraded to `br_cond` here — a conditional branch is required to have a resolvable condition for the misprediction scenario to be meaningful.

**Mode: `mispredict_taken` (future)**

The branch is NOT architecturally taken (`condition_value=False`), but the BTB predicts taken. At least one `noop` must be inserted before the architectural fall-through target, creating the speculative execution path. `btb_prediction = "taken"`. Not yet implemented.

**Output dict:** Same as pass 2, with these additions:

Top-level:
```python
{
"branch_mode": str, # "mispredict_not_taken" | "mispredict_taken"
"needs_end_block": bool, # True if any branch targets end_block
# ...all pass-2 fields preserved
}
```

Per unresolved branch instruction:

```python
{
"branch_annotations": {
"mode": str, # which mode was applied
"condition_value": bool, # what the condition resolves to
"taken_target": str, # label for the taken edge (e.g. "end_block")
"fallthrough_target": str, # label for the fall-through edge (e.g. "bb_1")
"btb_prediction": str, # "fall_through" | "taken"
"btb_predicted_pc": int, # simulator override: PC the BTB predicts as next
},
# concrete_instruction may have been upgraded from br_uncond to br_cond
}
```

**Key design choices:**
- The `btb_predicted_pc` field in `branch_annotations` is the primary hook for the simulator. At simulation time, overwrite this with whatever PC you want the BTB to report — this forces the desired speculation direction without needing to train a predictor.
- `needs_end_block` tells the IR emitter to append a bare `end_block:` label with `ret i64 0` after all instruction blocks. Branches target this label as their architectural destination.
- The basic block structure implied by this pass: all instructions before and including the branch are in the entry block; all instructions after it are in a speculative block (`bb_{pc+1}`); both eventually terminate at `end_block`.

---

### 2.1.4 Pass 3 — Assign concrete registers and memory

**Function:** `pass3_assign_operands(pass25_result, out_path, write_out)`

**Input:** Pass 2.5 dict.

**What it does:**
Fully assigns every active operand slot to a concrete register name or memory byte offset. After this pass, the dict contains all information needed to emit LLVM IR (modulo SSA renaming, which is pass 4).
#### Register assignment
**Available pool:** x86-64 System V ABI caller-saved registers — the registers a function may freely clobber without saving/restoring:
```
rax rcx rdx rsi rdi r8 r9 r10 r11 (9 total)
```
(Argument registers `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` plus `rax`, `r10`, `r11`.)

**Locked registers (specified, `Reg_s$*` physical):** Assigned to real physical registers from this list in sorted `Reg_s$*` order: `Reg_s$0 → rax`, `Reg_s$1 → rcx`, etc. These are stored in `result["locked_registers"]`. In the final LLVM IR, writes to these registers will be forced via inline-asm output constraints (`"={rax}"` etc.) so that two instructions sharing a `Reg_s$*` atom in the Alloy model literally alias in the physical register file — required for correct microarchitectural behavior.

**Free pool for unspecified registers:** Size = 9 − (number of locked registers). Drawn from `X86_64_CALLER_SAVED[n_locked_regs:]` — the real physical x86 register names left over after locked registers claim the front of the list. For example, if one register is locked (`rax`), the free pool is `["rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"]`. This means all registers in the program — both Alloy-specified (locked) and unspecified (free) — come from the same master `X86_64_CALLER_SAVED` list (`["rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"]`); locked registers take the front N entries, the free pool is the remaining entries. The pool is exactly large enough so that, no matter how many unique register names are used, the LLVM backend can assign each to a distinct physical register without spilling. Unspecified register slots that are in the concrete instruction's `uses` set are randomly sampled from this pool. Because every assigned register name is a real physical name, pass 5 can force every outreg write into a specific physical register via `"={phys},r"` inline asm without requiring any LLVM backend reservation pass.

**Unused slots** (not in the concrete instruction's `uses`): `assigned = None`. The IR emitter ignores them.

#### Memory assignment

A single base `alloca` holds all memory locations as an array of `i64` values (8 bytes each, sequential offsets: 0, 8, 16, …). All memory accesses in the generated LLVM IR use GEP into this alloca.

**Locked memory (specified, `Mem_s$*` physical):** Fixed offset in the alloca, in sorted `Mem_s$*` order: `Mem_s$0 → offset 0`, `Mem_s$1 → offset 8`, etc. Two instructions that share a `Mem_s$*` atom get the same offset — they access the same physical memory location, as required by the Alloy model. Stored in `result["memory_offsets"]`.

**Unspecified memory** (in a slot the concrete instruction uses): Each gets its own fresh offset, allocated sequentially after the locked slots. No two unspecified slots share an offset.

**Unused memory slots** (not in `uses`): `assigned_offset = None`. Ignored by the IR emitter.

**Alloca sizing:** `result["alloca_total_bytes"]` is computed after processing all instructions. The IR emitter should prepend the alloca declaration (sized to this value) at the start of the function.

#### Branch conditions

For instructions with `branch_annotations`, the forced condition constant is propagated into `instruction["condition_assigned"]` (bool). The IR emitter uses this to initialize the branch's condition register to the right value before the branch.

**Output dict:**

```python
{
"instructions": [ ... ], # all slot dicts gain "assigned" (reg) or "assigned_offset" (mem)
"resource_usage": { ... }, # unchanged from pass 1
"branch_mode": str,
"needs_end_block": bool,
"locked_registers": { # Reg_s$* atom -> physical register name
"Reg_s$0": "rax", ...
},
"virtual_reg_pool": list, # actual physical register names from X86_64_CALLER_SAVED[n_locked:], e.g. ["rcx", "rdx", ...]
"memory_offsets": { # Mem_s$* atom -> byte offset in alloca
"Mem_s$0": 0, ...
},
"alloca_total_bytes": int, # total size of the single base alloca
"alloca_total_slots": int, # number of i64 slots in the alloca
}
```

Per register slot dict: `"assigned": str | None`

Per memory slot dict: `"assigned_offset": int | None`

Per branch instruction with `branch_annotations`: `"condition_assigned": bool`

**Key design choices:**

- The free pool size cap is the critical anti-spill guarantee. Having more assigned register names than available physical registers would force LLVM to spill to the stack, which would corrupt the microarchitectural test by introducing unexpected memory traffic. By capping the free pool to the physical registers not already claimed by locked registers, spillage is structurally impossible. The anti-spill guarantee is unchanged from the previous design; only the mechanism differs — all names are now real physical names rather than synthetic `rx*` names, so the LLVM register allocator has no ambiguity about which physical register each name maps to.

- Unspecified memory slots intentionally never alias (each gets a unique offset). Creating aliasing between unspecified locations would introduce unintended memory dependencies between instructions that the Alloy model didn't assert. Aliasing only occurs where Alloy explicitly required it via shared `Mem_s$*` atoms.

- The `inaddr` slot (the register holding a memory address) is treated purely as a register assignment here. The semantic constraint that the value of the `inaddr` register must equal the pointer to the corresponding `inmem`/`outmem` offset is left for the IR emitter to enforce by generating a GEP instruction.

- `volatile` is already embedded in the `llvm_op` strings for memory instructions (`"load volatile i64"`, `"store volatile i64"`), preventing the LLVM optimizer from eliminating or reordering them.

---

### 2.1.5 Pass 4 — SSA renaming

**Function:** `pass4_ssa(pass3_result, out_path, write_out)`

**Input:** Pass 3 dict.

**What it does:**

Converts the register names assigned in pass 3 (which may be written multiple times by different instructions) into proper SSA form, where each value is defined exactly once and every use refers to a specific definition. LLVM IR requires SSA form.

Since the program is a linear sequence (topologically sorted by `spo` with no back-edges), SSA construction is purely linear — no phi nodes are needed. Even with branches (from pass 2.5), the basic block structure is:

- Entry block → (taken) end_block, or (fall-through) speculative block

- Speculative block → end_block

- end_block: `ret i64 0` (no values consumed)

Because `end_block` consumes no SSA values, there is no merge point requiring a phi node. SSA renaming proceeds as a single left-to-right scan.

**SSA renaming algorithm:**

Walk instructions in PC order. For each instruction:

1. **Read phase:** For each input slot (`inreg0`, `inreg1`, `inaddr`) that is active (in `uses` and `assigned != None`), look up the current SSA name for that register. If the register has never been written yet, create a version-0 name (`{reg}_0`) and record it in `ssa_init`.

2. **Write phase:** For each output slot (`outreg`) that is active, create a fresh SSA name (`{reg}_{n+1}`) and update the current mapping for that register.

Reads are resolved before writes so that an instruction reading and writing the same register (e.g. `add rx0, rx0`) correctly uses the old value on the input and defines a new value on the output.

**SSA name format:** `{reg_name}_{version}` — e.g. `rax_0` (init), `rax_1`, `rx0_1`, `rx0_2`. No `%` prefix is stored in the dict; the IR emitter prepends `%` when emitting text.

Memory slots (`inmem`, `outmem`) carry byte offsets, not values. They are not renamed and receive no `ssa_name`.

**`ssa_init`:** A dict of `{ register_name → version-0 SSA name }` for every register that was read before its first write. The IR emitter must emit an initialization for each at the start of the function body:

- **Locked register** (name appears in `locked_registers.values()`): initialize via inline-asm output constraint, e.g. force `rax` to hold a specific value.

- **Virtual register** (`rx*`): emit `%{name} = add i64 0, 0` as a zero-initialization placeholder.

**Branch condition handling:**

For any instruction with `condition_assigned`, a new field is added:

```python
instruction["condition_ssa_forced"] = "i1 true" # or "i1 false"
```

This tells the IR emitter to use this LLVM constant directly as the `br i1` operand (rather than the register's SSA value), so that:

1. The condition is architecturally correct (branch is taken when `True`).

2. The branch cannot be constant-folded away before reaching the microarchitectural simulator.

The `inreg0` SSA name is still computed for bookkeeping (it tracks which register the Alloy model placed the condition value in), but `condition_ssa_forced` is what gets emitted.

**Output dict:**

```python
{
"instructions": [ ... ], # all active register slot dicts gain "ssa_name": str | None
"resource_usage": { ... },
"branch_mode": str,
"needs_end_block": bool,
"locked_registers": { ... }, # unchanged from pass 3
"virtual_reg_pool": list,
"memory_offsets": { ... },
"alloca_total_bytes": int,
"alloca_total_slots": int,
"ssa_init": { # registers needing initialization before first instruction
"rax": "rax_0",
"rx3": "rx3_0", ...
}
}
```

Per active register slot: `"ssa_name": str | None` (None if `assigned=None`)

Per branch instruction with `branch_annotations`: `"condition_ssa_forced": "i1 true" | "i1 false"`

**Key design choices:**

- The reason locked registers need inline-asm at write sites (not just at read sites) is microarchitectural: two Alloy instructions sharing `Reg_s$0` must literally write to and read from the same physical register file location. SSA correctly models the value-flow chain but does not, on its own, guarantee a specific physical register. The inline-asm `"={rax}"` constraint forces the LLVM register allocator to place that SSA value in `%rax`. Read sites do not need constraints because once the SSA value is known to live in `%rax` (from the write constraint), all uses of that SSA value automatically read from `%rax`.

- A reserved register list in the LLVM backend is also needed for locked registers. The inline-asm constraint pins a value to `%rax` while it is live, but if there is a "dead gap" between when one instruction writes `Reg_s$0` and the next reads it, the register allocator could legally use `%rax` for an unrelated temporary. The reserved list prevents this for the entire function.

---

### 2.1.6 Pass 5 — Emit LLVM IR

**Function:** `pass5_emit_llvm(pass4_result, func_name, out_path, write_out)`

**Input:** Pass 4 dict.

**Output:** LLVM IR string (and optionally a `.ll` file). A single function `@{func_name}() -> i64`.

**What it does:**

Walks the SSA-annotated instruction list and emits valid LLVM IR. The output can be passed directly to `clang` or `llc`. Produces one function with an `entry:` block, optional intermediate basic blocks (`bb_{pc}:`), and an optional `end_block:` epilogue.

#### Entry block structure

```llvm
define i64 @test() {
entry:
; 1. alloca — single [N x i64] array covering all memory slots
%mem_base = alloca [N x i64], align 8
; 2. zero-init each memory slot with a volatile store (prevents optimizer elimination)
%__mg_1 = getelementptr [N x i64], ptr %mem_base, i64 0, i64 0
store volatile i64 0, ptr %__mg_1, align 8
...
; 3. ssa_init — zero-initialize registers read before first write
;    all registers use inline asm movq to force a specific physical register
%rax_0 = call i64 asm sideeffect "movq $1, $0", "={rax},r"(i64 0)
%rcx_0 = call i64 asm sideeffect "movq $1, $0", "={rcx},r"(i64 0)
```

The alloca covers `alloca_total_slots` i64 slots (= `alloca_total_bytes / 8`). Each slot is GEP-indexed (0-based). The GEP index for a given load/store comes from `inmem.assigned_offset // 8` or `outmem.assigned_offset // 8`.

#### Per-instruction emission

For each instruction (in PC order):

- If `pc` is in the set of fallthrough targets from mispredicted branches, emit a block label `bb_{pc}:` first.

- Emit a comment `; pc={pc} {atom} ({concrete_instruction})`.

- Then emit the concrete IR:
| Concrete instruction | IR emitted |
|---|---|
| `load` | GEP from `inmem.assigned_offset`, then `load volatile i64, ptr %gep` |
| `store` | GEP from `outmem.assigned_offset`, then `store volatile i64 %inreg0_ssa, ptr %gep` |
| `bitnot` | `xor i64 %inreg0_ssa, -1` |
| `add` | `add i64 %inreg0_ssa, %inreg1_ssa` |
| `br_cond` (mispredicted) | `br i1 true, label %{taken}, label %{fallthrough}` with BTB comment |
| `br_cond`/`br_uncond` (resolved) | comment only — linear flow continues |

**All outreg writes:** For every instruction that writes an output register, the result is first computed into a temporary SSA value, then forced into the physical register via inline asm. This applies unconditionally to all outreg-writing instructions (load, bitnot, add), regardless of whether the register is Alloy-locked or from the free pool:

```llvm
%__xor_1 = xor i64 %rcx_0, -1
%rax_1 = call i64 asm sideeffect "movq $1, $0", "={rax},r"(i64 %__xor_1)
```

The `movq $1, $0` in AT&T syntax moves the input register (`$1`) into the output register (`$0` = the named physical register). The constraint string `"={rax},r"` declares the output writes to `%rax` and the input comes from any general register. Because all assigned registers are now real physical names, the `"={phys},r"` constraint can be applied uniformly without any special-casing.

**Mispredicted branches:** Use `condition_ssa_forced` (`"i1 true"` or `"i1 false"`) directly, not a register value. This ensures the condition is architecturally correct and cannot be constant-folded away before reaching the simulator. A comment records the BTB prediction and the simulator override point:

```llvm
; BTB predicts=fall_through btb_predicted_pc=1
br i1 true, label %end_block, label %bb_1
```

#### Epilogue

After the last instruction:

- If `needs_end_block` is True (any branch targets `end_block`): emit `br label %end_block` if the last instruction was not already a terminator, then emit `end_block: ret i64 0`.

- Otherwise: emit `ret i64 0` directly.

#### Full example output

Program with one mispredicted branch (Branchx$0) followed by a load (Load$0) where the load output is a locked register:

```llvm
define i64 @test() {
entry:
%mem_base = alloca [1 x i64], align 8
%__mg_1 = getelementptr [1 x i64], ptr %mem_base, i64 0, i64 0
store volatile i64 0, ptr %__mg_1, align 8
%rax_0 = call i64 asm sideeffect "movq $1, $0", "={rax},r"(i64 0)
; pc=0 Branchx$0 (br_cond)
; BTB predicts=fall_through btb_predicted_pc=1
br i1 true, label %end_block, label %bb_1
bb_1:
; pc=1 Load$0 (load)
%__gep_1 = getelementptr [1 x i64], ptr %mem_base, i64 0, i64 0
%__ld_1 = load volatile i64, ptr %__gep_1, align 8
%rax_1 = call i64 asm sideeffect "movq $1, $0", "={rax},r"(i64 %__ld_1)
br label %end_block
end_block:
ret i64 0
}
```

**Output:** The function returns a string containing the full LLVM IR. If `write_out=True` and `out_path` is provided, the IR is also written to that path.

**Key design choices:**

- GEP (not `inttoptr` of the `inaddr` register) is used as the actual pointer for loads and stores. This guarantees valid addresses at runtime regardless of what value the `inaddr` register was initialized to. The `inaddr` slot still carries its SSA value for tracking which physical register holds the address conceptually, but the pointer operand in the IR is computed fresh from the alloca.

- All memory ops are `volatile` to prevent the LLVM optimizer from removing or reordering them. Without `volatile`, LLVM may CSE multiple loads from the same address or eliminate dead stores, corrupting the microarchitectural test.

- Resolved branches are emitted as comments and do not break the basic block. LLVM IR validity is maintained because the linear instruction stream remains in the current block until a real terminator is emitted.

- All outreg writes use `sideeffect` inline asm with a specific physical register constraint (`"={phys},r"`), not just Alloy-locked ones. This ensures every register-writing instruction survives LLVM's SelectionDAG even at O0, where truly dead DAG nodes can be pruned. It also eliminates the need for a reserved-register pass in the LLVM backend, since all registers (locked and free) are forced to their physical name at every write site.

- The `"sideeffect"` keyword on all inline asm calls prevents LLVM from treating them as pure computations and removing them if their outputs appear unused.

---

### 2.1.7 Side output — Branch annotation file

**Function:** `emit_branch_annotations(result, out_path, write_out)`

**Input:** Any pipeline result dict from pass 2.5 or later (the `branch_annotations` field is preserved through passes 3, 4, and 5).

**Output:** A list of annotation dicts (one per unresolved branch, in PC order), and optionally a JSON file.

**What it does:**

Collects the BTB force annotation for every unresolved branch. This is the second output of the pipeline alongside the LLVM IR — the simulator reads it to know which BTB entries to override before running the test.

For each instruction that has `branch_annotations`, records:
| Field | Type | Description |
|---|---|---|
| `branch_pc` | int | PC index (0-based) of the branch instruction |
| `branch_atom` | str | Alloy atom name, e.g. `"Branchx$0"` |
| `btb_forced_target_pc` | int | The PC index the simulator should force the BTB to predict as the next instruction |
| `mode` | str | Misprediction mode, e.g. `"mispredict_not_taken"` |

The `btb_forced_target_pc` is the wrong target — the one the BTB will incorrectly report, causing speculative execution to begin from that PC. The simulator forces a "taken" prediction to this address; because it is the wrong target, this constitutes a misprediction regardless of the branch's actual direction.

The `btb_forced_target_pc` is expressed as a PC index into the instruction sequence. The simulator is responsible for resolving this to an actual memory address at load time (e.g. by looking up the address of the instruction at that index in the compiled binary).

**JSON output format:**

```json
{
  "branch_mode": "mispredict_not_taken",
  "annotations": [
    {
      "branch_pc": 0,
      "branch_atom": "Branchx$0",
      "btb_forced_target_pc": 1,
      "mode": "mispredict_not_taken"
    },
    {
      "branch_pc": 1,
      "branch_atom": "Branchx$1",
      "btb_forced_target_pc": 2,
      "mode": "mispredict_not_taken"
    }
  ]
}
```

**Typical usage (paired with pass 5):**

```python
ir = pass5_emit_llvm(r4, func_name="test", out_path="out.ll", write_out=True)
emit_branch_annotations(r4, out_path="out.ann.json", write_out=True)
```

**Key design choices:**

- `emit_branch_annotations` is not a pipeline pass — it does not transform the data dict. It is a formatter that can be called on any result ≥ pass 2.5 without modifying pipeline state.

- The address is expressed as a PC index, not a raw memory address, because actual addresses are not known until link time. The simulator bridges the gap by mapping PC indices to addresses after loading the compiled binary.

- Only unresolved branches (those with `branch_annotations`) appear in the output. Resolved branches are correctly predicted by definition and require no BTB override.