All passes live in `STAGE2_compilation/parsexml.py`. Each pass takes the output dict of the previous pass and returns an enriched dict. Passes can optionally write a human-readable `.ir` text file (`write_out=True`, `out_path=...`). The full pipeline in order:

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

**Input:** An `AlloyInstance` produced by `parse_alloy_xml(xml_text)`, which parses raw Alloy XML. The XML contains the Alloy model's solution using the **kind-field** encoding: all instructions are atoms of a single concrete `Instruction` sig, and each has a `kind` field pointing to one of six `InstrType` one-sigs (`TLoad`, `TStore`, `TBranchn`, `TBranchx`, `TOthern`, `TOtherx`). The XML also contains state atoms (`Reg_s$*`, `Mem_s$*`), operand atoms (`Inreg$*`, `Outreg$*`, `Inmem$*`, `Outmem$*`, `Inaddr$*`), and relations between them (`spo`, `kind`, `inreg`, `outreg`, `inmem`, `outmem`, `inaddr`, `opstate`, `isresolved`, `iscommitted`, `isxm`).

**What it does:**
1. Collects all instruction atoms from the single `this/Instruction` sig.
2. Looks up each instruction's kind via the `kind` field relation, then maps the `InstrType` atom to a kind token using `_TYPE_TAG_TO_KIND` (e.g. `TLoad$0` → `"ld"`, `TBranchx$0` → `"br_x"`).
3. Topologically sorts instructions by the `spo` (speculative program order) relation to produce a linear execution order.
4. For each instruction, maps its operand atoms (e.g. `Inreg$0`) to their physical state via the `opstate` relation. A physical state is either a `Reg_s$*` atom (register location) or a `Mem_s$*` atom (memory location). This distinction is what makes two operands "the same physical location."
5. Populates slot records for each operand role. Every instruction has the same fixed set of roles: `inreg` (2 slots: `inreg0`, `inreg1`), `inaddr` (1 slot), `inmem` (1 slot), `outreg` (1 slot), `outmem` (1 slot). A slot is **specified** if the Alloy model assigned it a physical state, and **nonspecified** otherwise.
6. Collects the set of unique physical register states (`Reg_s$*`) and memory states (`Mem_s$*`) used across all instructions.
7. Records the `isxm` flag (transmitter tag) from the Alloy model for each instruction.

**Output dict:**
```python
{
"instructions": [
{
"pc": int, # position in topological order
"instruction": str, # atom name, e.g. "Instruction$0"
"kind": str, # "ld" | "str" | "br_n" | "br_x" | "other_n" | "other_x"
"resolved": bool, # from isresolved relation
"committed": bool, # from iscommitted relation
"xm": bool, # from isxm relation — True if this is the tagged transmitter
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
- `resolved`, `committed`, and `xm` flags are preserved through all subsequent passes — they are the primary microarchitectural metadata the pipeline is designed around.
- The kind-field model uses a single concrete `Instruction` sig (not abstract + subsigs). This enables symmetry-breaking via IX position atoms in the Alloy model. The kind token is derived from the `kind` field relation, not from sig membership.

---
### 2.1.2 Pass 2 — Specify concrete instruction types

**Function:** `pass2_specify_instructions(pass1_result, instruction_table, out_path, write_out)`
**Input:** Pass 1 dict.
**What it does:**
Assigns a concrete LLVM-level instruction type to each abstract instruction atom. Uses an `INSTRUCTION_TABLE` loaded at startup from `instruction_tables/instructions.jsonc`. The JSON file defines a `kind_categories` mapping and per-category instruction candidates. Each candidate declares which operand slots it uses (`"uses"` set).

The instruction table is loaded via `_load_instruction_tables()` which reads the JSONC file (stripping comments), parses `kind_categories` and converts each candidate's `uses` array to a set. The table can be reloaded at runtime via `reload_tables(path)` to point at an alternate JSON without editing source.

**Kind category mapping** (from `kind_categories` in JSON):

| Kind token | Category |
| ---------- | -------- |
| `ld`       | `ld`     |
| `str`      | `str`    |
| `br_n`     | `br`     |
| `br_x`     | `br`     |
| `other_n`  | `other_n`|
| `other_x`  | `other_x`|

Note: `other_n` and `other_x` are **separate categories**, each with their own candidate lists. This allows different instruction options for transmitting vs non-transmitting ALU ops.

**Instruction candidates** (from `instructions` in JSON):

| Category  | Concrete name | `llvm_op`            | `uses` (slot names)        |
| --------- | ------------- | -------------------- | -------------------------- |
| `ld`      | `load`        | `load volatile i64`  | `{inaddr, inmem, outreg}`  |
| `str`     | `store`       | `store volatile i64` | `{inreg0, inaddr, outmem}` |
| `br`      | `br_uncond`   | `br label`           | `{}`                       |
| `br`      | `br_cond`     | `br i1`              | `{inreg0}`                 |
| `br`      | `br_bez`      | `testq+jz`           | `{}`                       |
| `other_n` | `bitnot`      | `xor i64`            | `{inreg0, outreg}`         |
| `other_n` | `add`         | `add i64`            | `{inreg0, inreg1, outreg}` |
| `other_x` | `bitnot`      | `xor i64`            | `{inreg0, outreg}`         |
| `other_x` | `add`         | `add i64`            | `{inreg0, inreg1, outreg}` |

**Filtering rule:** For a given abstract instruction, collect the set of slot names that are already specified (have a physical state from Alloy). Filter the category's candidates to those whose `uses` set is a **superset** of the specified slots — i.e. every slot the Alloy model has pinned must be consumed by the chosen instruction. Among valid candidates, choose **randomly** (using `random.choice`). If no candidate covers all specified slots (model/table inconsistency), fall back to all candidates.

Example: `Instruction$2` with kind `other_n` and `inreg0` specified → `bitnot` (uses `{inreg0, outreg}`) and `add` (uses `{inreg0, inreg1, outreg}`) are both valid; one is chosen at random. If `inreg1` were also specified, only `add` would be valid.

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

- The instruction table is externalized to JSON so new instruction types can be added without modifying parsexml.py. The `reload_tables()` function supports batch runs with alternate tables via `batch_generate --instruction-tables`.

---

### 2.1.3 Pass 2.5 — Annotate branch mispredictions

**Function:** `pass2_5_specify_branches(pass2_result, branch_mode, out_path, write_out)`

**Input:** Pass 2 dict.

**What it does:**
Annotates unresolved branch instructions (`resolved=False` and `kind` in `{"br_n", "br_x"}`) with misprediction metadata. Resolved branches pass through unchanged. All non-branch instructions pass through unchanged.

Only one mode is active: `branch_mode="mispredict_not_taken"`. A second mode (`mispredict_taken`) is there too.

**Mode: `mispredict_not_taken` (default)**
The branch IS architecturally taken (condition resolves to `True`), but the branch target buffer (BTB) predicts fall-through (not taken). The CPU therefore speculatively executes the instructions that follow the branch in program order (the fall-through path), then squashes that work when the branch resolves as taken.
- `condition_value = True` — the branch condition evaluates to true (branch taken)
- `taken_target = "end_block"` — the architectural destination label (a block appended after all instructions)
- `fallthrough_target = "bb_{pc+1}"` — the speculative execution path (next sequential instruction's block label); `"end_block"` if the branch is the last instruction
- `btb_prediction = "fall_through"` — what the BTB predicts
- `btb_predicted_pc = pc + 1` — **this is the simulator override point**: the PC the BTB thinks comes next. Overwrite this value in the simulator to change the BTB's prediction.

If pass 2 assigned `br_uncond` to an uncond branch (because no operands were specified), it is upgraded to `br_cond` here — a conditional branch is required to have a resolvable condition for the misprediction scenario to be meaningful.

**XM branch → `br_bez` upgrade:** If the unresolved branch is the xmit transmitter (`xm=True`), it is further upgraded to `br_bez` (branch-if-equal-to-zero). This uses the `testq+jz` pattern: all registers are zero-initialised, so `testq %reg, %reg` sets ZF=1 and `jz` is taken. The BTB predicts not-taken (fall-through), creating the misprediction. This gives the branch itself a data-dependent timing signal (the condition load misses cache), making it a valid transmitter.

**Synthetic NOP injection:** If an xm branch is the last instruction or the next instruction is also a branch, a synthetic NOP instruction is injected on the fall-through path. This ensures the speculative execution path has an instruction for the processor to fetch (and squash). The NOP record has `kind="other_n"`, `concrete_instruction="nop"`, and `synthetic=True`.

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
# concrete_instruction may have been upgraded from br_uncond to br_cond to br_bez
}
```

**Key design choices:**
- The `btb_predicted_pc` field in `branch_annotations` is the primary hook for the simulator. At simulation time, overwrite this with whatever PC you want the BTB to report — this forces the desired speculation direction without needing to train a predictor.
- `needs_end_block` tells the IR emitter to append a bare `end_block:` label with `ret i64 0` after all instruction blocks. Branches target this label as their architectural destination.
- The `br_bez` upgrade for xm branches ensures the branch instruction itself is a transmitter — its data-dependent condition load (from a cache-flushed slot) creates an observable timing difference. This is distinct from `br_cond` where the condition is a constant `i1 true`.
- Synthetic NOPs are marked `synthetic=True` so downstream passes can identify them. They have empty `slots` dicts since they use no operands.

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

**Virtual pool and reserved registers:** The remaining entries of `X86_64_CALLER_SAVED[n_locked_regs:]` form the `virtual_reg_pool`. The first 3 entries are **reserved for code-generation infrastructure** and must never be assigned to instruction operand slots:

| Index | Constant | Purpose |
|-------|----------|---------|
| 0 | `_VPOOL_IDX_SCRATCH` | Branch: clflush base pointer register |
| 1 | `_VPOOL_IDX_COND_REG` | Branch: condition-load destination register |
| 2 | `_VPOOL_IDX_PROBE_BASE` | Load/store: base pointer for `probe_mem` or `mem_base` |

This separation ensures locked (Alloy-tracked, potentially tainted) registers are never aliased by compiler-generated pointer materializations, which would create spurious taint via gem5's Lea-merge (`Data = merge(Data, ea, dataSize)`) micro-op.

**Free pool for unspecified registers:** Size = `len(virtual_pool) - 3`. Drawn from `virtual_pool[_VPOOL_FREE_START:]` — the physical register names left after locked registers and the 3 reserved slots. Unspecified register slots that are in the concrete instruction's `uses` set are randomly sampled from this pool. Because every assigned register name is a real physical name, pass 5 can force every outreg write into a specific physical register via inline asm without requiring any LLVM backend reservation pass.

**Unused slots** (not in the concrete instruction's `uses`): `assigned = None`. The IR emitter ignores them.

#### Memory assignment

A single base `alloca` holds all memory locations as an array of `i64` values (8 bytes each, sequential offsets: 0, 8, 16, …). All memory accesses in the generated LLVM IR use GEP into this alloca.

**Locked memory (specified, `Mem_s$*` physical):** Fixed offset in the alloca, in sorted `Mem_s$*` order: `Mem_s$0 → offset 0`, `Mem_s$1 → offset 8`, etc. Two instructions that share a `Mem_s$*` atom get the same offset — they access the same physical memory location, as required by the Alloy model. Stored in `result["memory_offsets"]`.

**Unspecified memory** (in a slot the concrete instruction uses): Each gets its own fresh offset, allocated sequentially after the locked slots. No two unspecified slots share an offset.

**Unused memory slots** (not in `uses`): `assigned_offset = None`. Ignored by the IR emitter.

**Alloca sizing:** `result["alloca_total_bytes"]` is computed after processing all instructions. The IR emitter should prepend the alloca declaration (sized to this value) at the start of the function body. The operand pool is capped in the Alloy model to the number of available physical registers, so spills are structurally impossible.

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
"virtual_reg_pool": list, # physical register names from X86_64_CALLER_SAVED[n_locked:], e.g. ["rcx", "rdx", ...]
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

- The 3-register reserved prefix in the virtual pool is the anti-taint-leak guarantee. Without it, LLVM could choose a locked register for a `leaq` used to materialize a pointer, which would merge the pointer's address into the locked register via gem5's `Lea-merge` micro-op, creating spurious taint.

- Unspecified memory slots intentionally never alias (each gets a unique offset). Creating aliasing between unspecified locations would introduce unintended memory dependencies between instructions that the Alloy model didn't assert. Aliasing only occurs where Alloy explicitly required it via shared `Mem_s$*` atoms.

- The `inaddr` slot (the register holding a memory address) is treated purely as a register assignment here. The semantic constraint that the value of the `inaddr` register must equal the pointer to the corresponding `inmem`/`outmem` offset is left for the IR emitter to enforce by generating the appropriate addressing mode.

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

Reads are resolved before writes so that an instruction reading and writing the same register (e.g. `add rax, rax`) correctly uses the old value on the input and defines a new value on the output.

**SSA name format:** `{reg_name}_{version}` — e.g. `rax_0` (init), `rax_1`, `rcx_1`. No `%` prefix is stored in the dict; the IR emitter prepends `%` when emitting text. All names use real physical register names (not synthetic `rx*` names).

Memory slots (`inmem`, `outmem`) carry byte offsets, not values. They are not renamed and receive no `ssa_name`.

**`ssa_init`:** A dict of `{ register_name → version-0 SSA name }` for every register that was read before its first write. The IR emitter must emit an initialization for each at the start of the function body using inline-asm `movq` with a physical register constraint (e.g. `"={rax},r"` with `i64 0`).

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
"rcx": "rcx_0", ...
}
}
```

Per active register slot: `"ssa_name": str | None` (None if `assigned=None`)

Per branch instruction with `branch_annotations`: `"condition_ssa_forced": "i1 true" | "i1 false"`

**Key design choices:**

- The reason locked registers need inline-asm at write sites (not just at read sites) is microarchitectural: two Alloy instructions sharing `Reg_s$0` must literally write to and read from the same physical register file location. SSA correctly models the value-flow chain but does not, on its own, guarantee a specific physical register. The inline-asm `"={rax}"` constraint forces the LLVM register allocator to place that SSA value in `%rax`. Read sites do not need constraints because once the SSA value is known to live in `%rax` (from the write constraint), all uses of that SSA value automatically read from `%rax`.

---

### 2.1.6 Pass 5 — Emit LLVM IR

**Function:** `pass5_emit_llvm(pass4_result, func_name, out_path, write_out)`

**Input:** Pass 4 dict.

**Output:** LLVM IR string (and optionally a `.ll` file). A single function `@{func_name}() -> i64`.

**What it does:**

Walks the SSA-annotated instruction list and emits valid LLVM IR. The output can be passed directly to `clang` or `llc`. Produces one function with an `entry:` block, optional intermediate basic blocks (`bb_{pc}:`), and an optional `end_block:` epilogue.

**All instructions are emitted as inline assembly** (`asm sideeffect`) to guarantee exact control over register allocation, instruction ordering, and prevent LLVM from rewriting, reordering, or eliminating instructions.

#### Entry block structure

```llvm
define i64 @test() {
entry:
; 1. alloca — single [N x i64] array covering all memory slots
%mem_base = alloca [N x i64], align 8
; 2. zero-init each memory slot with a volatile store
%__mg_1 = getelementptr [N x i64], ptr %mem_base, i64 0, i64 0
store volatile i64 0, ptr %__mg_1, align 8
...
; 3. probe array — 256 cache-line-separated i64 slots for Spectre probe pattern
;    (only emitted if any load/store has a specified inaddr)
%probe_mem = alloca [256 x i64], align 64
; (each slot zero-initialized)
...
; 4. ssa_init — zero-initialize registers read before first write
;    ALL use inline asm movq to force a specific physical register
%rax_0 = call i64 asm sideeffect "movq $1, $0", "={rax},r"(i64 0)
%rcx_0 = call i64 asm sideeffect "movq $1, $0", "={rcx},r"(i64 0)
; 5. condition slots — one cache-line-aligned i64 per mispredicted branch
;    (flushed from cache at the branch site to maximise speculation window)
%cond_slot_pc0 = alloca i64, align 64
store volatile i64 1, ptr %cond_slot_pc0, align 64   ; br_cond: init 1 (icmp ne → true)
; or: store volatile i64 0 ...                        ; br_bez: init 0 (icmp eq → true)
```

The alloca covers `alloca_total_slots` i64 slots (= `alloca_total_bytes / 8`). The probe array is `[256 x i64]` aligned to 64 bytes (cache-line stride) for the canonical Spectre access pattern.

#### PC markers

Every emitted instruction includes a global label marking its position in the compiled binary:

```asm
.globl __litmus_{func}_pc{pc}
__litmus_{func}_pc{pc}:
```

Additionally, the last committed and first non-committed instructions get extra markers:

```asm
.globl __litmus_{func}_last_committed
__litmus_{func}_last_committed:
.globl __litmus_{func}_first_noncommitted
__litmus_{func}_first_noncommitted:
```

These markers are embedded in the inline asm string prefix so nothing (GEP, icmp, etc.) can appear between the label and the actual instruction in compiled output.

#### Per-instruction emission

For each instruction (in PC order):

- If `pc` is in the set of fallthrough targets from mispredicted branches, emit a block label `bb_{pc}:` first.

- Emit a comment `; pc={pc} {atom} ({concrete_instruction})`.

- Then emit the concrete inline asm:

| Concrete instruction | Emitted asm | Notes |
|---|---|---|
| `load` (no inaddr) | `movq {offset}(%probe_base), %dst` | Fixed offset from `mem_base` via reserved `probe_base` register |
| `load` (inaddr specified) | `movq (%probe_base, %secret, 1), %dst` | Spectre probe: secret value as byte offset into `probe_mem` |
| `store` (no inaddr) | `movq %src, {offset}(%probe_base)` | Fixed offset from `mem_base` |
| `store` (inaddr specified) | `movq %src, (%probe_base, %secret, 1)` | Secret-indexed store into `probe_mem` |
| `bitnot` (same in/out reg) | `notq %reg` | In-place NOT |
| `bitnot` (diff in/out reg) | `movq %src, %dst; notq %dst` | Copy then NOT |
| `add` | `leaq (%src1, %src2), %dst` | Uses LEA to avoid flag side-effects |
| `br_cond` (mispredicted) | `mfence; clflush (slot); mfence; movq (slot), %cond; icmp ne 0; br` | Cache-miss condition load maximises speculation window |
| `br_bez` (xm mispredicted) | `mfence; clflush (slot); mfence; movq (slot), %cond; testq; jz` | Same but branch-if-zero; slot init'd to 0 |
| `br_cond`/`br_uncond` (resolved) | comment only | No branch emitted; linear flow continues |
| `nop` (synthetic) | `nop` | Fall-through target for xm branches |

**Mispredicted branch pattern (detail):**

```llvm
; Flush the condition slot from cache to maximise speculation window
call void asm sideeffect "mfence\0Aclflush ($0)\0Amfence",
  "{scratch},~{memory}"(ptr %cond_slot)
; Slow load — cache miss (~200-300 cycles speculation window)
%cond_raw = call i64 asm sideeffect "movq ($1), $0",
  "=&{cond_reg},{scratch},~{memory}"(ptr %cond_slot)
; Compare and branch
%cond_i1 = icmp ne i64 %cond_raw, 0    ; (or icmp eq for br_bez)
br i1 %cond_i1, label %end_block, label %bb_{pc+1}
```

The `scratch` and `cond_reg` registers come from the virtual pool's reserved indices (positions 0 and 1), ensuring they never overlap with locked test registers.

**All outreg writes** are forced into physical registers via inline asm output constraints (`"=&{phys}"`). The `=&` (early-clobber) ensures the output register is not aliased with any input register by the compiler.

#### Epilogue

After the last instruction:

- If `needs_end_block` is True: emit `br label %end_block` if the last instruction was not already a terminator, then emit `end_block: ret i64 0`.

- Otherwise: emit `ret i64 0` directly.

#### Full example output

Program with one mispredicted branch (xm, br_bez) followed by a load where the load output is a locked register:

```llvm
define i64 @test() {
entry:
%mem_base = alloca [1 x i64], align 8
%__mg_1 = getelementptr [1 x i64], ptr %mem_base, i64 0, i64 0
store volatile i64 0, ptr %__mg_1, align 8
%rax_0 = call i64 asm sideeffect "movq $1, $0", "={rax},r"(i64 0)
%cond_slot_pc0 = alloca i64, align 64
store volatile i64 0, ptr %cond_slot_pc0, align 64
; pc=0  Instruction$0  (br_bez)
; BEZ xmit branch: BTB predicts=fall_through
call void asm sideeffect ".globl __litmus_test_pc0\0A__litmus_test_pc0:\0Amfence\0Aclflush ($0)\0Amfence", "{r10},~{memory}"(ptr %cond_slot_pc0)
%__bez_raw_1 = call i64 asm sideeffect "movq ($1), $0", "=&{r11},{r10},~{memory}"(ptr %cond_slot_pc0)
%__bez_i1_1 = icmp eq i64 %__bez_raw_1, 0
br i1 %__bez_i1_1, label %end_block, label %bb_1
bb_1:
; pc=1  Instruction$1  (load)
%rax_1 = call i64 asm sideeffect ".globl __litmus_test_pc1\0A__litmus_test_pc1:\0Amovq 0($1), $0", "=&{rax},{r8},~{memory}"(ptr %mem_base)
br label %end_block
end_block:
ret i64 0
}
```

**Output:** The function returns a string containing the full LLVM IR. If `write_out=True` and `out_path` is provided, the IR is also written to that path.

**Key design choices:**

- **All-inline-asm emission:** Every instruction is emitted as `asm sideeffect` to give exact control over which physical registers are read/written, prevent LLVM from rewriting or eliminating instructions, and ensure the compiled output matches the Alloy model's microarchitectural intent. This replaces the earlier approach of using LLVM IR instructions (load, xor, add, br) with post-hoc inline asm pinning.

- **Probe array for inaddr loads/stores:** When `inaddr` is specified (has an rf edge from another instruction's output), the secret value is used as a byte offset into a 256-slot probe array (`movq (%probe_base, %secret, 1), %dst`). Different secret values hit different cache lines, creating the canonical Spectre side channel. When `inaddr` is not specified, loads/stores use fixed offsets from `mem_base`.

- **Reserved `probe_base` register:** The `_VPOOL_IDX_PROBE_BASE` register (virtual pool index 2) is used for all `mem_base` and `probe_mem` pointer materializations. Using an explicit physical register instead of LLVM's `"r"` wildcard prevents the compiler from choosing a locked register for `leaq` address computations, which would create spurious taint.

- **Cache-flush branch conditioning:** The `mfence; clflush; mfence; movq` sequence ensures the condition value is loaded from DRAM (not cache), creating a ~200-300 cycle speculation window. The condition slot is `align 64` so `clflush` targets exactly one cache line.

- **LEA for add:** `leaq (%src1, %src2), %dst` is used instead of `addq` because LEA doesn't modify flags. This avoids unintended flag dependencies between instructions.

- **Early-clobber (`=&`):** All output constraints use `=&` to prevent the compiler from assigning the same physical register to both an input and the output, which would corrupt the input value before use.

- All memory ops are `volatile` to prevent the LLVM optimizer from removing or reordering them.

- Resolved branches are emitted as comments (just the PC marker) and do not break the basic block.

- The `"sideeffect"` keyword on all inline asm calls prevents LLVM from treating them as pure computations and removing them if their outputs appear unused.

---

### 2.1.7 Side output — Branch annotation file

**Function:** `emit_branch_annotations(result, out_path, write_out)`

**Input:** Any pipeline result dict from pass 2.5 or later (the `branch_annotations` field is preserved through passes 3, 4, and 5).

**Output:** A list of annotation dicts (one per unresolved branch, in PC order), and optionally a JSON file.

**What it does:**

Collects the BTB force annotation for every unresolved branch, plus metadata about the xmit instruction and commit boundary. This is the second output of the pipeline alongside the LLVM IR — the simulator reads it to know which BTB entries to override before running the test.

For each instruction that has `branch_annotations`, records:

| Field | Type | Description |
|---|---|---|
| `branch_pc` | int | PC index (0-based) of the branch instruction |
| `branch_atom` | str | Alloy atom name, e.g. `"Instruction$0"` |
| `btb_forced_target_pc` | int | The PC index the simulator should force the BTB to predict as the next instruction |
| `mode` | str | Misprediction mode, e.g. `"mispredict_not_taken"` |

The `btb_forced_target_pc` is the wrong target — the one the BTB will incorrectly report, causing speculative execution to begin from that PC.

**Additional JSON fields:**

The JSON output also includes:

- `xmit`: `{ "pc": int, "kind": str, "atom": str }` — the instruction tagged with `isxm` in the Alloy model (at most one per instance, enforced by `fact one_xm`).

- `commit_boundary`: `{ "last_committed": { "pc": int, "atom": str }, "first_noncommitted": { "pc": int, "atom": str } }` — the boundary between committed and speculative instructions in program order.

**JSON output format:**

```json
{
  "branch_mode": "mispredict_not_taken",
  "annotations": [
    {
      "branch_pc": 0,
      "branch_atom": "Instruction$0",
      "btb_forced_target_pc": 1,
      "mode": "mispredict_not_taken"
    }
  ],
  "xmit": {
    "pc": 2,
    "kind": "other_x",
    "atom": "Instruction$2"
  },
  "commit_boundary": {
    "last_committed": { "pc": 0, "atom": "Instruction$0" },
    "first_noncommitted": { "pc": 1, "atom": "Instruction$1" }
  }
}
```

**Key design choices:**

- `emit_branch_annotations` is not a pipeline pass — it does not transform the data dict. It is a formatter that can be called on any result ≥ pass 2.5 without modifying pipeline state.

- The address is expressed as a PC index, not a raw memory address, because actual addresses are not known until link time. The simulator bridges the gap by mapping PC indices to addresses after loading the compiled binary (using the `__litmus_*_pc{N}` global symbols emitted by pass 5).

- Only unresolved branches (those with `branch_annotations`) appear in the annotations list. Resolved branches are correctly predicted by definition and require no BTB override.

- The `xmit` and `commit_boundary` fields give the simulator the information needed to configure the microarchitectural observation harness (e.g., which instruction to monitor for leakage, where to set the commit boundary in the ROB model).
