This document outlines the goal of SimSpect as well as the major functionality and design choices of the test generation and execution pipeline. 

**Goal**: For a proposed Spectre defense with defined security guarantees and a gem5 simulator implementation, generate and execute a defense-specific and leakage-targeted set of assembly litmus tests, to discover security contract violations in the implementation.
## Background
### Helper definitions
**Transmitters**: instructions that leak one or more operands via a HSC
**Speculation primitives:** instructions that initiate speculative executions, e.g., a conditional branch
**Access instructions:** #towrite
**HSCA:** Hardware side channel attack
**HSCD:** Hardware side channel defense (can be implemented in **hardware**, software, or **both**)
**DUT:** Defense under test, a proposed hardware side channel defense that employs hardware modification implemented for proof of concept in the gem5 architectural simulator. See below for discussions of defense scope
**Security contract:** The defined Spectre security guarantees of the defense, formalized by [[#1.1 Security contract]].
**Leakage path (LP):** The series of elements (instructions + their operands and state) that contribute to a microarchitectural leakage event.
### Executions vs. tests
**Program execution:** A snapshot of an assembly program at a specific cycle during its execution. Includes instructions, with metadata at the granularity of speculation direction and resolution, as well as committed status #towrite word this better. We need this metadata because the leakage we are studying occurs in the microarchitecture, so we are validating not on architectural outputs but on the occurrence of a particular microarchitectural state at some point in time. These are the minimal metadata components we deem necessary for the contract testing we are doing. #designchoice
**Litmus testing:** Litmus testing is the practice of running suites of (typically small and/or targeted) programs on an implementation under test to validate its functionality. #towrite cite and write this better.
**LILT: Leakage-inducing litmus tests** An execution is not a program. We want to generate programs to run on our implementation that *target* a particular microarchitectural execution. However, to have the best chance of inducing microarchitectural speculation and hitting the desired metadata state in this execution, we wish to grant ourselves control of microarchitectural knobs. These knobs include fixing branch predictor outcomes (to induce misprediction) both in direction and target, as well as fixing store set predictors for STL forwarding prediction (the mechanism for this is a separate point — we take advantage of the fact that we are operating on a simulator, which is a white box, to directly force these predictions, but one could also do this by training a predictor in the case where this instrumentation is not available, say while testing hardware #designchoice). Our LILTs therefore contain two components: an assembly program to be run, and an annotation which dictates speculation direction. They also have an output of sorts to check, not an architectural output, but rather they check that their #towrite #todo we will need to check that the committed instructions are committed and that nothing leaks when the program occurs as promised #designchoice. We initially generate abstracted target executions, then derive LILTs that target them.
# 1: Generation
#input*DUT with natural-language security guarantees* and a hardware proof-of-concept implementation in gem5**
#output*Set of program executions in Alloy xml output, with abstract instructions and partially specified state, as well as resolution and committed flags*
Our goal is to trigger leaking program **executions** by generating leakage-inducing **tests**. #todo repetitive. An **execution** in its final form as run on gem5 is an assembly program with annotations of speculation-force (mem and ctrl). In this generation phase, we generate all abstract executions in a particular syntax that contain a minimal leakage path as defined by the defense. See [[#1.2 Alloy]] for discussions of minimality.
## 1.1 Security contract
#input *Proposed Spectre defense natural-language security guarantees* 
#output *Formal specification in the Alloy execution syntax of the three security properties*
The goal is to define the security contract of each defense in the following three definitions. 
1. **Leakage contract:** A leakage contract is the set of pairs of *transmitters* (instructions that leak one or more operands via a hardware side channel) and their unsafe operand(s), as recognized by the defense.
2. **Execution contract:** An execution contract characterizes what speculative control- and data-flow is allowed on the microarchitecture by identifying what *speculation primitives* (instructions that initiate speculative executions, e.g., a conditional branch) the defense considers. 
3. **Protection set:** A protection set is the set of architectural state (memory and registers) that the defense promises to not leak architecturally and/or speculatively. Along with the protection set we encode a protection set update rule, that represents the updates that a given protection set undergoes with each instruction.
This definition is done manually.
## 1.2 Alloy
#input *Formal specification in the Alloy execution syntax of the three security properties*
#output *Set of program executions in Alloy xml output, with abstract instructions and partially specified state, as well as resolution and committed flags*
The defense-specific **protection set, leakage contract,** and **execution contract** are defined in the syntax of an execution. Then the Alloy Analyzer axiomatic model finder is used to enumerate all the possible abstract executions that contain a leakage path made up of these three components, and are minimal according to some metric. 
### 1.2.1 Execution syntax
In the generation phase we are only specifying instructions to the degree that a HSCD would differentiate. We do this to keep forms of violations limited, leaving enumeration across instruction types to the concretization phase of the pipeline #designchoice. The syntax of an abstract execution is as follows:

**Nodes:**
Instructions:
- Xmit
	- Ld
	- Str
	- Br
	- Other
- Non-xmit
	- Br
	- Other
State
- Reg
- Mem
Operands
- inmem
- inreg
- inaddr
- outreg
- outmem

An execution is made up of a series of instructions connected via spo which have some operands that are specific to that instruction and point to a state

**Booleans**
- committed (out of ROB, non-spec)
	- contiguous at end of SPO
- resolved
	- br knows target and condition
	- ld str knows address

**Edges**
- ordering
	- spo (i->i): speculative program order, defines the order of instructions #designchoice just including SPO vs PO, because we are targeting an execution
	- rf (o->o): reads-from relationship between output and input operands of instructions, used to calculate dataflow from protected state
	- ddi (o->o): data-dependence internal, relationship between input and output operands of the same instruction, used to calculate dataflow from protected state

**Instruction constraints**

| instr   | ops+xmits(*)              | dependency generation |
| ------- | ------------------------- | --------------------- |
| ld      | inaddr*, inmem, outreg    | ALLMEM->outreg        |
| str     | inaddr\*, inreg\*, outmem | inreg->outmem         |
| br_x    | inreg*                    |                       |
| other_x | inreg*, outreg            | inreg->outreg         |
| br_n    | inreg                     |                       |
| other_n | inreg, outreg             | inreg->outreg         |
#designchoice ld dependency generation assumption, #todo check if this is correct
### 1.2.2 Minimality
If we were to generate every execution up to a bound that contained a violating path, our test set, while it would be targeted, would be too large to feasibly run on our implementation. We adopt a method of relaxation that we model off of Lustig et al #todo cite in their work on memory consistency model verification. 
We degrade all of our tests within some set of relaxations until every component of the test is necessary for the leakage to occur, so that we do not include more state than we need. 
The space of relaxations is as follows:
- **Remove Instructions (RI):** remove an instruction from the test
- **Remove Operand (RO):** remove an operand from an instruction (link between instruction and state)
- **Remove State (RS):** remove a state element from the system
- **Shift Commit (RC):** make the last uncommitted instruction committed (only relevant when the execution contract uses the commit label/head of ROB)
- **Make Resolved (RR):** make an unresolved instruction resolved (only relevant when the execution contract uses resolved, note you can't do RC and RR at the same time. #todo need to do disjunction)
### 1.2.3 State specification
Classes of state: 
a. necessary for the leakage path
b. unnecessary for the leakage path

|                         | operand on LP | operand off LP but uses a | operand off LP no a |
| ----------------------- | ------------- | ------------------------- | ------------------- |
| **Instr on LP**         | ==y==         | ==?==                     | ?                   |
| **Instr off LP uses a** | ==n==         | ==y==                     | ?                   |
| **Instr off LP no a**   | n             | n                         | y                   |
Yellow boxes specified by the alloy model. We allow our model to be a little bigger than the minimal set of instructions, as long as all instructions use some amount of relevant state. This is because we can interleave later with irrelevant instructions in the concretization phase, and also flesh out irrelevant operands from that unassigned state space. We only need to make a statement about the existence of a leakage path, so we must determine all the state that has to do with that path and protect it in the Alloy phase such that we have complete control that it will leak. This method allows us to add spacer instructions that could interact with the leakage path without bloat. 
This approach leaves us with the following relaxations enabled: 
- **RS:** all state elements are necessary to the leakage path
- no **RI:** we can contain extra instructions as long as they have at least one necessary state operand
	- Fact {no Instructions - operands.Operand}
- no **RO:** we can contain extra operands as long as they have necessary state
	- Fact {no Operand - opstate.State}
- Execution contract
	- either **RR** or **RC**, depending on which one the execution contact utilizes, and if it uses both we have to say RR or RC fails but if both fail it doesn't matter
# 2: Concretization
#input*Set of program executions in Alloy xml output, with abstract instructions and partially specified state, as well as resolution and committed flags*
#output*Set of LILTs designed to trigger the input program executions, each consisting of a program with annotated speculation state*
## 2.1 Passes

All passes live in `alloy/parsexml.py`. Each pass takes the output dict of the previous pass and returns an enriched dict. Passes can optionally write a human-readable `.ir` text file (`write_out=True`, `out_path=...`). The full pipeline in order:

```
Alloy XML
  → Pass 1   pass1_specify_state_a
  → Pass 2   pass2_specify_instructions
  → Pass 2.5 pass2_5_specify_branches
  → Pass 3   pass3_assign_operands
  → Pass 4   pass4_ssa
  → Pass 5   pass5_emit_llvm          → LLVM IR text (.ll)
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
      "pc": int,                  # position in topological order
      "instruction": str,         # atom name, e.g. "Load$0"
      "kind": str,                # "ld" | "str" | "br_n" | "br_x" | "other_n" | "other_x"
      "resolved": bool,           # from isresolved relation
      "committed": bool,          # from iscommitted relation
      "slots": {
        "inreg":  [ {slot, specified, operand_atom, physical}, ... ],  # 2 entries
        "inaddr": [ {slot, specified, operand_atom, physical} ],        # 1 entry
        "inmem":  [ {slot, specified, operand_atom, physical} ],        # 1 entry
        "outreg": [ {slot, specified, operand_atom, physical} ],        # 1 entry
        "outmem": [ {slot, specified, operand_atom, physical} ]         # 1 entry
      }
    }, ...
  ],
  "resource_usage": {
    "register_count": int,        # number of unique Reg_s$* atoms
    "memory_count": int,          # number of unique Mem_s$* atoms
    "registers": [ "Reg_s$0", ... ],  # sorted list
    "memory":    [ "Mem_s$0", ... ]   # sorted list
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

| Category | Concrete name | `llvm_op` | `uses` (slot names) |
|---|---|---|---|
| `ld` | `load` | `load volatile i64` | `{inaddr, inmem, outreg}` |
| `str` | `store` | `store volatile i64` | `{inreg0, inaddr, outmem}` |
| `br` | `br_uncond` | `br label` | `{}` |
| `br` | `br_cond` | `br i1` | `{inreg0}` |
| `other` | `bitnot` | `xor i64` | `{inreg0, outreg}` |
| `other` | `add` | `add i64` | `{inreg0, inreg1, outreg}` |

Kind tokens are normalized to categories first: `br_n`/`br_x` → `br`, `other_n`/`other_x` → `other`.

**Filtering rule:** For a given abstract instruction, collect the set of slot names that are already specified (have a physical state from Alloy). Filter the category's candidates to those whose `uses` set is a **superset** of the specified slots — i.e. every slot the Alloy model has pinned must be consumed by the chosen instruction. Among valid candidates, choose **randomly** (using `random.choice`). If no candidate covers all specified slots (model/table inconsistency), fall back to all candidates.

Example: `Otherx$0` with `inreg0` specified → `bitnot` (uses `{inreg0, outreg}`) and `add` (uses `{inreg0, inreg1, outreg}`) are both valid; one is chosen at random. If `inreg1` were also specified, only `add` would be valid.

**Output dict:** Same structure as pass 1, with three fields added to each instruction record:
```python
{
  "concrete_instruction": str,   # e.g. "load", "bitnot", "br_cond"
  "llvm_op":              str,   # e.g. "load volatile i64", "xor i64"
  "candidates":           list,  # all valid concrete names for this instruction
  # ...all pass-1 fields preserved unchanged
}
```

**Key design choices:**
- The `uses` set controls which operand slots will actually appear in the final emitted instruction. Slots not in `uses` are never assigned real values and are marked `None` in later passes. This prevents wasted register/memory allocations.
- Randomness is at the instruction level. Re-running the pipeline with a different random seed produces different concrete instruction assignments where there is choice.

---

### 2.1.3 Pass 2.5 — Annotate branch mispredictions
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
  "branch_mode":     str,    # "mispredict_not_taken" | "mispredict_taken"
  "needs_end_block": bool,   # True if any branch targets end_block
  # ...all pass-2 fields preserved
}
```

Per unresolved branch instruction:
```python
{
  "branch_annotations": {
    "mode":               str,   # which mode was applied
    "condition_value":    bool,  # what the condition resolves to
    "taken_target":       str,   # label for the taken edge (e.g. "end_block")
    "fallthrough_target": str,   # label for the fall-through edge (e.g. "bb_1")
    "btb_prediction":     str,   # "fall_through" | "taken"
    "btb_predicted_pc":   int,   # simulator override: PC the BTB predicts as next
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
rax  rcx  rdx  rsi  rdi  r8  r9  r10  r11      (9 total)
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
  "instructions": [ ... ],      # all slot dicts gain "assigned" (reg) or "assigned_offset" (mem)
  "resource_usage": { ... },    # unchanged from pass 1
  "branch_mode": str,
  "needs_end_block": bool,
  "locked_registers": {         # Reg_s$* atom -> physical register name
    "Reg_s$0": "rax", ...
  },
  "virtual_reg_pool": list,     # actual physical register names from X86_64_CALLER_SAVED[n_locked:], e.g. ["rcx", "rdx", ...]
  "memory_offsets": {           # Mem_s$* atom -> byte offset in alloca
    "Mem_s$0": 0, ...
  },
  "alloca_total_bytes": int,    # total size of the single base alloca
  "alloca_total_slots": int,    # number of i64 slots in the alloca
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
instruction["condition_ssa_forced"] = "i1 true"  # or "i1 false"
```
This tells the IR emitter to use this LLVM constant directly as the `br i1` operand (rather than the register's SSA value), so that:
1. The condition is architecturally correct (branch is taken when `True`).
2. The branch cannot be constant-folded away before reaching the microarchitectural simulator.

The `inreg0` SSA name is still computed for bookkeeping (it tracks which register the Alloy model placed the condition value in), but `condition_ssa_forced` is what gets emitted.

**Output dict:**
```python
{
  "instructions": [ ... ],      # all active register slot dicts gain "ssa_name": str | None
  "resource_usage": { ... },
  "branch_mode": str,
  "needs_end_block": bool,
  "locked_registers": { ... },  # unchanged from pass 3
  "virtual_reg_pool": list,
  "memory_offsets": { ... },
  "alloca_total_bytes": int,
  "alloca_total_slots": int,
  "ssa_init": {                 # registers needing initialization before first instruction
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
- Emit a comment `; pc={pc}  {atom}  ({concrete_instruction})`.
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
  ; BTB predicts=fall_through  btb_predicted_pc=1
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
  ; pc=0  Branchx$0  (br_cond)
  ; BTB predicts=fall_through  btb_predicted_pc=1
  br i1 true, label %end_block, label %bb_1
bb_1:
  ; pc=1  Load$0  (load)
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

## 2.2 B

# 3: Simulation
## 3.1 Formatting programs
## 3.2 Fixing speculation
### 3.2.1 Ctrl


## 3.3 Observing outputs


#designchoice
#impl
#todo
#towrite


# Design choices
## Execution contract:
In testing we are broadly faced with the question of whether we will test to the conservative extent of the security contract, or to the space of possible leakage that intersects with the security contract.
### Gem5 speculation primitives and execution contract
The execution contract (defining which circumstances cause an instruction to be speculative) is defined in each defense in a conservative overarching definition. However, the effective space of *real* leakage is the intersection of the speculation in this contract and the speculation possible in gem5 (the *speculation primitives*)

We therefore distinguish two possible ways we could test a defense execution contract: 
1. test the execution contract broadly as specified by the defense
2. test the execution contract as projected onto *real speculation* in the gem5 speculation primitives
Option 2 is more gracious to the implementers, because it focuses on real bugs, but it is perhaps incomplete because the format of the defense implementation should theoretically cover the whole promised space of leakage, and should therefore match the broader execution contract. 
![[Pasted image 20260227143758.png]]
### Misprediction vs. correct prediction
We could test that the defense prevents leakage under speculation that will resolve to be incorrect (mispredicted taken, mispredicted not taken), but we could also test that the defense prevents leakage under speculation that will resolve to be correct, while it is speculative. This is another execution contract interpretation question. 
### Dependency chains
Even under actual speculation, if the window is conservative (e.g. any instruction that follows an unresolved load, even things that don't depend that load) we have the same issue. Does a real leakage path have to exist in our test that could arise and leak on the defense, or are we encroaching upon the defense's ability to specify its own security contract by deigning to define *real* leakage. We should have the opportunity to test both directions for all of these divides, and make a reasonable first assumption. 

Right now there exists two versions of many models, one that contains the raw execution contract and the other that contains the intersected execution contract. This design choice also arises in the non-Alloy later stages as well though, and is yet to be 100% resolved. 
## Scope of defenses
#towrite
[[Defense security contracts]]

## Bounds
- How long of tests we run

## todo:
- appendix of all the studied defenses and their contracts
- numbers on the defenses we have pushed through the pipeline
-

## questions
- what if it's not possible for a program to complete

- would we ever want excess unresolved instructions 