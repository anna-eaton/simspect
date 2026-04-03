from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple, Optional
import xml.etree.ElementTree as ET
import re
import random

# HELPERS
# -----------------------------
# Parse Alloy XML helper
# -----------------------------
@dataclass
class AlloyInstance:
    sig_atoms: Dict[str, Set[str]]
    fields: Dict[str, List[Tuple[str, ...]]]


def parse_alloy_xml(xml_text: str) -> AlloyInstance:
    root = ET.fromstring(xml_text)

    sig_atoms: Dict[str, Set[str]] = {}
    fields: Dict[str, List[Tuple[str, ...]]] = {}

    for sig in root.iter("sig"):
        label = sig.attrib.get("label", "")
        atoms = set()
        for atom in sig.findall("atom"):
            atoms.add(atom.attrib["label"])
        sig_atoms[label] = atoms

    for field in root.iter("field"):
        flabel = field.attrib.get("label", "")
        tups: List[Tuple[str, ...]] = []
        for tup in field.findall("tuple"):
            atoms = [a.attrib["label"] for a in tup.findall("atom")]
            tups.append(tuple(atoms))
        fields[flabel] = tups

    return AlloyInstance(sig_atoms=sig_atoms, fields=fields)

# -----------------------------
# Toposort helper
# -----------------------------
def topo_sort(nodes: List[str], edges: List[Tuple[str, str]]) -> List[str]:
    adj: Dict[str, List[str]] = {n: [] for n in nodes}
    indeg: Dict[str, int] = {n: 0 for n in nodes}
    for a, b in edges:
        if a not in adj:
            adj[a] = []
            indeg[a] = 0
        if b not in adj:
            adj[b] = []
            indeg[b] = 0
        adj[a].append(b)
        indeg[b] += 1

    q = [n for n in nodes if indeg.get(n, 0) == 0]
    out: List[str] = []
    while q:
        n = q.pop()
        out.append(n)
        for m in adj.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)

    if len(out) != len(set(nodes)):
        raise ValueError("spo graph is not a DAG or nodes list is incomplete.")

    return out

# -----------------------------
# LLVM emission helper
# -----------------------------
def llvm_escape(name: str) -> str:
    return name.replace("$", "_")


def _atom_sort_key(atom: str) -> Tuple[str, int, str]:
    m = re.match(r"^(.*)\$(\d+)$", atom)
    if not m:
        return (atom, -1, atom)
    prefix, num = m.group(1), int(m.group(2))
    return (prefix, num, atom)


def _build_rel_map(pairs: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for left, right in pairs:
        out.setdefault(left, []).append(right)
    for k in out:
        out[k] = sorted(out[k], key=_atom_sort_key)
    return out


# Maps InstrType atom base labels to kind tokens.
# Alloy labels one-sig atoms with a $0 suffix (e.g. TLoad$0); we strip it.
_TYPE_TAG_TO_KIND: Dict[str, str] = {
    "TLoad":    "ld",
    "TStore":   "str",
    "TBranchn": "br_n",
    "TBranchx": "br_x",
    "TOthern":  "other_n",
    "TOtherx":  "other_x",
}

def _kind_token(ins: str, kind_of: Dict[str, str]) -> str:
    """Look up kind token via the kind field dict (kind-model variant)."""
    tag = kind_of.get(ins, "")
    base = tag.split("$")[0] if "$" in tag else tag
    return _TYPE_TAG_TO_KIND.get(base, "unknown")


def _format_slots(
    role: str,
    operands: List[str],
    opstate_of: Dict[str, str],
    slot_count: int,
) -> List[str]:
    fields: List[str] = []
    for idx in range(slot_count):
        slot_name = f"{role}{idx}" if slot_count > 1 else role
        if idx < len(operands):
            op = operands[idx]
            physical = opstate_of.get(op, op)
            fields.append(f"{slot_name}=specified:{physical}")
        else:
            fields.append(f"{slot_name}=nonspecified")
    return fields


def _build_slot_records(
    role: str,
    operands: List[str],
    opstate_of: Dict[str, str],
    slot_count: int,
) -> List[Dict[str, Any]]:
    slots: List[Dict[str, Any]] = []
    for idx in range(slot_count):
        slot_name = f"{role}{idx}" if slot_count > 1 else role
        if idx < len(operands):
            op_atom = operands[idx]
            physical = opstate_of.get(op_atom, op_atom)
            slots.append(
                {
                    "slot": slot_name,
                    "specified": True,
                    "operand_atom": op_atom,
                    "physical": physical,
                }
            )
        else:
            slots.append(
                {
                    "slot": slot_name,
                    "specified": False,
                    "operand_atom": None,
                    "physical": None,
                }
            )
    return slots


# -----------------------------
# PHASE 1: specify mem and reg from alloy
#   - save them to a reserved list
#   - make sure that the code is specified
#   - save this incomplete program to an xml or asm?? file
#     - to have the ability to find duplicates from alloy
# PHASE 2: 
# -----------------------------
def pass1_specify_state_a(
    inst: AlloyInstance,
    out_path: Optional[str] = "alloy-out/spo_program.ir",
    write_out: bool = True,
) -> Dict[str, Any]:
    # kind-model: all instructions are in this/Instruction; type comes from kind field
    instr_atoms: Set[str] = set(inst.sig_atoms.get("this/Instruction", set()))

    # Build kind_of: {instruction_atom -> InstrType_atom} from the kind field
    kind_of: Dict[str, str] = {ins: tag for ins, tag in inst.fields.get("kind", [])}

    nodes = sorted(instr_atoms, key=_atom_sort_key)
    spo_edges = [
        (a, b)
        for (a, b) in inst.fields.get("spo", [])
        if a in instr_atoms and b in instr_atoms
    ]
    order = topo_sort(nodes, spo_edges)

    inregs_of = _build_rel_map(inst.fields.get("inreg", []))
    inaddrs_of = _build_rel_map(inst.fields.get("inaddr", []))
    inmems_of = _build_rel_map(inst.fields.get("inmem", []))
    outregs_of = _build_rel_map(inst.fields.get("outreg", []))
    outmems_of = _build_rel_map(inst.fields.get("outmem", []))

    opstate_of: Dict[str, str] = {}
    for op, st in inst.fields.get("opstate", []):
        opstate_of[op] = st

    resolved_instrs = {ins for (ins, _) in inst.fields.get("isresolved", [])}
    committed_instrs = {ins for (ins, _) in inst.fields.get("iscommitted", [])}
    xm_instrs        = {ins for (ins, _) in inst.fields.get("isxm",        [])}

    reg_states = inst.sig_atoms.get("this/Reg_s", set())
    mem_states = inst.sig_atoms.get("this/Mem_s", set())
    used_regs: Set[str] = set()
    used_mems: Set[str] = set()

    lines: List[str] = []
    lines.append("# SPO Abstract Program (phase 1)")
    lines.append("# state elements are physical locations from opstate")
    lines.append("")

    instruction_records: List[Dict[str, Any]] = []

    slot_shape = {
        "inreg": 2,
        "inaddr": 1,
        "inmem": 1,
        "outreg": 1,
        "outmem": 1,
    }

    for pc, ins in enumerate(order):
        kind = _kind_token(ins, kind_of)
        resolved_bool  = ins in resolved_instrs
        committed_bool = ins in committed_instrs
        xm_bool        = ins in xm_instrs
        resolved  = "true" if resolved_bool  else "false"
        committed = "true" if committed_bool else "false"

        inregs = inregs_of.get(ins, [])
        inaddrs = inaddrs_of.get(ins, [])
        inmems = inmems_of.get(ins, [])
        outregs = outregs_of.get(ins, [])
        outmems = outmems_of.get(ins, [])

        for op in inregs + inaddrs + outregs:
            st = opstate_of.get(op)
            if st in reg_states:
                used_regs.add(st)
        for op in inmems + outmems:
            st = opstate_of.get(op)
            if st in mem_states:
                used_mems.add(st)

        fields: List[str] = []
        fields.extend(_format_slots("inreg", inregs, opstate_of, slot_shape["inreg"]))
        fields.extend(_format_slots("inaddr", inaddrs, opstate_of, slot_shape["inaddr"]))
        fields.extend(_format_slots("inmem", inmems, opstate_of, slot_shape["inmem"]))
        fields.extend(_format_slots("outreg", outregs, opstate_of, slot_shape["outreg"]))
        fields.extend(_format_slots("outmem", outmems, opstate_of, slot_shape["outmem"]))

        slots: Dict[str, List[Dict[str, Any]]] = {
            "inreg": _build_slot_records("inreg", inregs, opstate_of, slot_shape["inreg"]),
            "inaddr": _build_slot_records("inaddr", inaddrs, opstate_of, slot_shape["inaddr"]),
            "inmem": _build_slot_records("inmem", inmems, opstate_of, slot_shape["inmem"]),
            "outreg": _build_slot_records("outreg", outregs, opstate_of, slot_shape["outreg"]),
            "outmem": _build_slot_records("outmem", outmems, opstate_of, slot_shape["outmem"]),
        }

        instruction_records.append(
            {
                "pc": pc,
                "instruction": ins,
                "kind": kind,
                "resolved":  resolved_bool,
                "committed": committed_bool,
                "xm":        xm_bool,
                "slots": slots,
            }
        )

        line = f"{pc:04d} {ins} {kind} resolved={resolved} committed={committed} " + " ".join(fields)
        lines.append(line)

    lines.append("")
    lines.append("# resource usage")
    lines.append(f"register_count={len(used_regs)}")
    lines.append(f"memory_count={len(used_mems)}")
    lines.append("registers=" + ",".join(sorted(used_regs, key=_atom_sort_key)))
    lines.append("memory=" + ",".join(sorted(used_mems, key=_atom_sort_key)))

    result: Dict[str, Any] = {
        "instructions": instruction_records,
        "resource_usage": {
            "register_count": len(used_regs),
            "memory_count": len(used_mems),
            "registers": sorted(used_regs, key=_atom_sort_key),
            "memory": sorted(used_mems, key=_atom_sort_key),
        },
    }

    if write_out:
        if out_path is None:
            raise ValueError("out_path must not be None when write_out=True")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return result


# =============================================================================
# Pass 2: assign concrete LLVM instructions
# =============================================================================

# Maps alloy kind tokens to instruction-table categories.
# br_n / br_x both map to "br"; other_n / other_x both map to "other".
_KIND_TO_CATEGORY: Dict[str, str] = {
    "ld":      "ld",
    "str":     "str",
    "br_n":    "br",
    "br_x":    "br",
    "other_n": "other",
    "other_x": "other",
    "unknown": "other",
}

# Instruction table.
# "uses": the set of operand-slot names this instruction consumes or produces.
# Slot names match what _build_slot_records emits: inreg0, inreg1, inaddr,
# inmem, outreg, outmem.
#
# Filtering rule: every specified slot on an abstract instruction must appear
# in the chosen candidate's "uses" set.  Among valid candidates, the one with
# the fewest entries in "uses" is preferred (simplest fit wins).
INSTRUCTION_TABLE: Dict[str, List[Dict[str, Any]]] = {
    "ld": [
        {
            "name": "load",
            "llvm_op": "load volatile i64",
            # reads address from inaddr (or inmem as the memory operand),
            # writes loaded value to outreg
            "uses": {"inaddr", "inmem", "outreg"},
        },
    ],
    "str": [
        {
            "name": "store",
            "llvm_op": "store volatile i64",
            # reads value from inreg0, address from inaddr, writes to outmem
            "uses": {"inreg0", "inaddr", "outmem"},
        },
    ],
    "br": [
        # Unconditional branch — no register operands
        {
            "name": "br_uncond",
            "llvm_op": "br label",
            "uses": set(),
        },
        # Conditional branch — consumes a condition value in inreg0
        {
            "name": "br_cond",
            "llvm_op": "br i1",
            "uses": {"inreg0"},
        },
    ],
    "other": [
        # Unary bitwise NOT (emitted as: %dst = xor i64 %src, -1)
        # Uses one input register and one output register.
        {
            "name": "bitnot",
            "llvm_op": "xor i64",
            "uses": {"inreg0", "outreg"},
        },
        # Binary integer add — uses two input registers and one output register.
        {
            "name": "add",
            "llvm_op": "add i64",
            "uses": {"inreg0", "inreg1", "outreg"},
        },
    ],
}


def pass2_specify_instructions(
    pass1_result: Dict[str, Any],
    instruction_table: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    out_path: Optional[str] = None,
    write_out: bool = False,
) -> Dict[str, Any]:
    """
    Pass 2: choose a concrete LLVM instruction for each abstract instruction.

    For each record from pass1:
      - Map its kind to a category (br_n/br_x -> br, other_n/other_x -> other).
      - Collect the set of slot names that are marked specified (e.g. {"inreg0"}).
      - Filter the category's candidates to those whose "uses" set is a superset
        of the specified slots — i.e. every specified operand must be consumed
        by the chosen instruction.
      - Among valid candidates, prefer the one with the fewest "uses" entries
        (simplest instruction that still satisfies all constraints).
      - Add concrete_instruction, llvm_op, and candidates to the record.

    Operand slots are left unchanged; most remain nonspecified.
    """
    if instruction_table is None:
        instruction_table = INSTRUCTION_TABLE

    output_instructions: List[Dict[str, Any]] = []

    for rec in pass1_result["instructions"]:
        kind = rec["kind"]
        category = _KIND_TO_CATEGORY.get(kind, "other")
        candidates = instruction_table.get(category, [])

        # Collect slot names that alloy has already pinned down
        specified_slots: Set[str] = set()
        for slot_list in rec["slots"].values():
            for sr in slot_list:
                if sr["specified"]:
                    specified_slots.add(sr["slot"])

        # Keep only candidates whose operand set covers every specified slot
        valid = [c for c in candidates if specified_slots <= c["uses"]]

        if not valid:
            # Table/model inconsistency: no candidate covers all specified slots.
            # Fall back to the full list so the pipeline can continue.
            valid = candidates

        # Pick randomly among valid candidates (all have >= the required operands)
        chosen = random.choice(valid) if valid else None

        out_rec = dict(rec)
        out_rec["concrete_instruction"] = chosen["name"] if chosen else None
        out_rec["llvm_op"] = chosen["llvm_op"] if chosen else None
        out_rec["candidates"] = [c["name"] for c in valid]
        output_instructions.append(out_rec)

    result: Dict[str, Any] = {
        "instructions": output_instructions,
        "resource_usage": pass1_result["resource_usage"],
    }

    if write_out:
        if out_path is None:
            raise ValueError("out_path must not be None when write_out=True")
        lines = ["# SPO Abstract Program (phase 2 - instruction assignment)"]
        lines.append("# concrete_instruction and llvm_op added; operands still mostly unspecified")
        lines.append("")
        for rec in output_instructions:
            concrete = rec.get("concrete_instruction") or "?"
            llvm_op  = rec.get("llvm_op") or "?"
            cands    = rec.get("candidates") or []
            slot_parts: List[str] = []
            for slot_list in rec["slots"].values():
                for sr in slot_list:
                    if sr["specified"]:
                        slot_parts.append(f"{sr['slot']}=specified:{sr['physical']}")
                    else:
                        slot_parts.append(f"{sr['slot']}=nonspecified")
            lines.append(
                f"{rec['pc']:04d} {rec['instruction']} "
                f"{rec['kind']}->{concrete} (llvm: {llvm_op}) "
                f"resolved={str(rec['resolved']).lower()} "
                f"committed={str(rec['committed']).lower()} "
                f"candidates=[{','.join(cands)}] "
                + " ".join(slot_parts)
            )
        lines.append("")
        ru = result["resource_usage"]
        lines.append(f"register_count={ru['register_count']}")
        lines.append(f"memory_count={ru['memory_count']}")
        lines.append("registers=" + ",".join(ru["registers"]))
        lines.append("memory=" + ",".join(ru["memory"]))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return result


# =============================================================================
# Pass 2.5: branch misprediction annotation
# =============================================================================

_BRANCH_KINDS = {"br_n", "br_x"}


def pass2_5_specify_branches(
    pass2_result: Dict[str, Any],
    branch_mode: str = "mispredict_not_taken",
    out_path: Optional[str] = None,
    write_out: bool = False,
) -> Dict[str, Any]:
    """
    Pass 2.5: annotate unresolved branch instructions with misprediction info.
    Resolved branches (resolved=True) pass through unchanged.

    branch_mode values
    ------------------
    "mispredict_not_taken"  (default, currently active)
        Branch IS architecturally taken (condition_value=True) so it jumps to
        taken_target="end_block" (a block appended past all instructions).
        The BTB predicts fall-through (not taken), so the CPU speculatively
        executes the instructions that follow the branch in program order
        (fallthrough_target="bb_<pc+1>"), then squashes on resolution.

        btb_prediction   = "fall_through"
        btb_predicted_pc = pc + 1   ← override this in the simulator to change
                                       what the BTB actually predicts

    "mispredict_taken"  (future, raises NotImplementedError)
        Branch is NOT architecturally taken (condition_value=False) but the
        BTB predicts taken. At least one noop will be inserted before the
        fall-through target. Stubbed pending a mode flag enabling it.

    Output dict additions
    ---------------------
    result["branch_mode"]      : str  — mode used for this run
    result["needs_end_block"]  : bool — True if any branch targets "end_block";
                                        the IR emitter must append that block

    Per unresolved branch, instruction["branch_annotations"] is added with:
        mode               str   which mode was applied
        condition_value    bool  what the condition resolves to architecturally
        taken_target       str   label name for the taken edge
        fallthrough_target str   label name for the fall-through edge
        btb_prediction     str   "fall_through" | "taken"
        btb_predicted_pc   int   PC the BTB thinks comes next
                                 ← this is the simulator override point

    If the concrete_instruction was "br_uncond" it is upgraded to "br_cond"
    because misprediction scenarios require a resolvable condition.
    """
    if branch_mode not in ("mispredict_not_taken", "mispredict_taken"):
        raise ValueError(f"Unknown branch_mode: {branch_mode!r}")
    if branch_mode == "mispredict_taken":
        raise NotImplementedError(
            "mispredict_taken is reserved for future implementation"
        )

    n = len(pass2_result["instructions"])
    instructions: List[Dict[str, Any]] = [dict(rec) for rec in pass2_result["instructions"]]
    needs_end_block = False

    for rec in instructions:
        if rec.get("kind") not in _BRANCH_KINDS:
            continue
        if rec.get("resolved", False):
            continue  # correctly-predicted branch, pass through unchanged

        pc = rec["pc"]
        next_pc = pc + 1

        # Misprediction requires a conditional branch; upgrade if pass 2 chose
        # the unconditional form because no operands were specified.
        if rec.get("concrete_instruction") == "br_uncond":
            rec["concrete_instruction"] = "br_cond"
            rec["llvm_op"] = "br i1"
            cands = rec.get("candidates", [])
            if "br_cond" not in cands:
                rec["candidates"] = cands + ["br_cond"]

        if branch_mode == "mispredict_not_taken":
            needs_end_block = True
            # If branch is the last instruction, fall-through also lands at end_block
            fallthrough = "end_block" if next_pc >= n else f"bb_{next_pc}"
            rec["branch_annotations"] = {
                "mode":               "mispredict_not_taken",
                "condition_value":    True,           # branch IS taken
                "taken_target":       "end_block",    # architectural destination
                "fallthrough_target": fallthrough,    # speculative execution path
                "btb_prediction":     "fall_through", # BTB predicts not taken
                "btb_predicted_pc":   next_pc,        # simulator override point
            }

    result: Dict[str, Any] = {
        "instructions": instructions,
        "resource_usage": pass2_result["resource_usage"],
        "branch_mode": branch_mode,
        "needs_end_block": needs_end_block,
    }

    if write_out:
        if out_path is None:
            raise ValueError("out_path must not be None when write_out=True")
        lines = ["# SPO Abstract Program (phase 2.5 - branch annotation)"]
        lines.append(f"# branch_mode: {branch_mode}")
        lines.append("")
        for rec in result["instructions"]:
            ba = rec.get("branch_annotations")
            slot_parts: List[str] = []
            for slot_list in rec["slots"].values():
                for sr in slot_list:
                    tag = f"specified:{sr['physical']}" if sr["specified"] else "nonspecified"
                    slot_parts.append(f"{sr['slot']}={tag}")
            line = (
                f"{rec['pc']:04d} {rec['instruction']} "
                f"{rec['kind']}->{rec.get('concrete_instruction', '?')} "
                f"resolved={str(rec['resolved']).lower()} "
                f"committed={str(rec['committed']).lower()} "
                + " ".join(slot_parts)
            )
            if ba:
                line += (
                    f" [BRANCH mode={ba['mode']}"
                    f" cond={ba['condition_value']}"
                    f" taken={ba['taken_target']}"
                    f" fallthrough={ba['fallthrough_target']}"
                    f" btb={ba['btb_prediction']}"
                    f" btb_pc={ba['btb_predicted_pc']}]"
                )
            lines.append(line)
        lines.append("")
        ru = result["resource_usage"]
        lines.append(f"register_count={ru['register_count']}")
        lines.append(f"memory_count={ru['memory_count']}")
        lines.append("registers=" + ",".join(ru["registers"]))
        lines.append("memory=" + ",".join(ru["memory"]))
        lines.append(f"needs_end_block={needs_end_block}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return result


# =============================================================================
# Pass 3: assign concrete operands
# =============================================================================

# x86-64 System V ABI caller-saved (volatile) registers.
# Argument registers : %rdi, %rsi, %rdx, %rcx, %r8, %r9
# Additional         : %rax (return value), %r10, %r11
X86_64_CALLER_SAVED: List[str] = [
    "rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"
]

_REG_SLOT_ROLES = {"inreg", "outreg", "inaddr"}
_MEM_SLOT_ROLES = {"inmem", "outmem"}


def _uses_for(concrete_instruction: Optional[str]) -> Set[str]:
    """Return the 'uses' set for a concrete instruction name from INSTRUCTION_TABLE."""
    if concrete_instruction is None:
        return set()
    for candidates in INSTRUCTION_TABLE.values():
        for c in candidates:
            if c["name"] == concrete_instruction:
                return c["uses"]
    return set()


def pass3_assign_operands(
    pass25_result: Dict[str, Any],
    out_path: Optional[str] = None,
    write_out: bool = False,
) -> Dict[str, Any]:
    """
    Pass 3: assign concrete register names and memory offsets to all slots.

    Registers
    ---------
    Locked (specified, Reg_s$* physical):
        Mapped to real x86-64 caller-saved registers in sorted Reg_s$* order.
        Stored in result["locked_registers"]  { Reg_s$* -> "rax" / ... }.
        These will be forced via inline-asm output constraints in the IR.

    Unspecified, slot IS used by the concrete instruction:
        Randomly sampled from the remaining entries of X86_64_CALLER_SAVED
        after locked registers are assigned.  These are real physical register
        names, so every outreg write can be forced via "={phys},r" inline asm
        without any LLVM backend reservation pass.

    Unspecified, slot NOT used by the concrete instruction:
        assigned = None  (IR emitter skips these).

    Memory
    ------
    Locked (specified, Mem_s$* physical):
        Fixed 8-byte slot in a single base alloca, in sorted Mem_s$* order.
        Stored in result["memory_offsets"]  { Mem_s$* -> byte_offset }.

    Unspecified, slot IS used by the concrete instruction:
        Each gets its own fresh 8-byte slot (never aliased).

    Unspecified, slot NOT used by the concrete instruction:
        assigned_offset = None  (IR emitter skips these).

    All register slot dicts gain  "assigned"        : str | None
    All memory slot dicts gain    "assigned_offset"  : int | None

    Alloca
    ------
    result["alloca_total_slots"]  : int   number of i64 slots
    result["alloca_total_bytes"]  : int   total byte size of the alloca

    Branch conditions
    -----------------
    For instructions with branch_annotations, the forced condition constant
    is also stored in  instruction["condition_assigned"]  (bool) so the IR
    emitter can substitute  i1 true / i1 false  instead of a register operand.
    """
    locked_reg_atoms: List[str] = pass25_result["resource_usage"]["registers"]
    locked_mem_atoms: List[str] = pass25_result["resource_usage"]["memory"]
    n_locked_regs = len(locked_reg_atoms)
    n_locked_mems = len(locked_mem_atoms)

    if n_locked_regs > len(X86_64_CALLER_SAVED):
        raise ValueError(
            f"Model uses {n_locked_regs} locked registers but only "
            f"{len(X86_64_CALLER_SAVED)} caller-saved registers are available"
        )

    # locked register map: Reg_s$* atom -> x86 physical name
    locked_reg_map: Dict[str, str] = {
        atom: X86_64_CALLER_SAVED[i] for i, atom in enumerate(locked_reg_atoms)
    }

    # Pool of physical registers available for unspecified slots —
    # the tail of X86_64_CALLER_SAVED after locked regs have claimed the front.
    n_free_regs = len(X86_64_CALLER_SAVED) - n_locked_regs
    virtual_pool: List[str] = X86_64_CALLER_SAVED[n_locked_regs:]

    # locked memory map: Mem_s$* atom -> byte offset
    locked_mem_map: Dict[str, int] = {
        atom: i * 8 for i, atom in enumerate(locked_mem_atoms)
    }

    free_mem_slot: int = n_locked_mems   # fresh slot counter, starts after locked

    instructions: List[Dict[str, Any]] = []

    for rec in pass25_result["instructions"]:
        new_rec = dict(rec)
        concrete = rec.get("concrete_instruction")
        uses = _uses_for(concrete)

        new_slots: Dict[str, List[Dict[str, Any]]] = {}
        for role, slot_list in rec["slots"].items():
            new_slot_list: List[Dict[str, Any]] = []
            for sr in slot_list:
                new_sr = dict(sr)
                slot_name = sr["slot"]   # e.g. "inreg0", "inmem", "outreg"

                if role in _REG_SLOT_ROLES:
                    if sr["specified"]:
                        # Locked: map to the assigned physical register
                        new_sr["assigned"] = locked_reg_map[sr["physical"]]
                    elif slot_name in uses:
                        # Used but free: sample from virtual pool
                        new_sr["assigned"] = random.choice(virtual_pool) if virtual_pool else None
                    else:
                        # Not used by this instruction
                        new_sr["assigned"] = None

                elif role in _MEM_SLOT_ROLES:
                    if sr["specified"]:
                        # Locked: fixed offset from the Mem_s$* map
                        new_sr["assigned_offset"] = locked_mem_map[sr["physical"]]
                    elif slot_name in uses:
                        # Used but free: allocate a fresh slot
                        new_sr["assigned_offset"] = free_mem_slot * 8
                        free_mem_slot += 1
                    else:
                        # Not used by this instruction
                        new_sr["assigned_offset"] = None

                new_slot_list.append(new_sr)
            new_slots[role] = new_slot_list

        new_rec["slots"] = new_slots

        # Branch: propagate forced condition constant for the IR emitter
        ba = rec.get("branch_annotations")
        if ba is not None:
            new_rec["condition_assigned"] = ba["condition_value"]

        instructions.append(new_rec)

    alloca_total_slots = free_mem_slot
    alloca_total_bytes = alloca_total_slots * 8

    result: Dict[str, Any] = {
        "instructions": instructions,
        "resource_usage": pass25_result["resource_usage"],
        "branch_mode": pass25_result.get("branch_mode"),
        "needs_end_block": pass25_result.get("needs_end_block", False),
        "locked_registers": locked_reg_map,
        "virtual_reg_pool": virtual_pool,
        "memory_offsets": locked_mem_map,
        "alloca_total_bytes": alloca_total_bytes,
        "alloca_total_slots": alloca_total_slots,
    }

    if write_out:
        if out_path is None:
            raise ValueError("out_path must not be None when write_out=True")
        pool_range = ", ".join(virtual_pool) if virtual_pool else "(empty)"
        lines = ["# SPO Abstract Program (phase 3 - operand assignment)"]
        lines.append(f"# locked_registers : {locked_reg_map}")
        lines.append(f"# virtual_pool     : {pool_range}")
        lines.append(f"# memory_offsets   : {locked_mem_map}")
        lines.append(f"# alloca           : {alloca_total_slots} x i64 = {alloca_total_bytes} bytes")
        lines.append("")
        for rec in instructions:
            slot_parts: List[str] = []
            for role, slot_list in rec["slots"].items():
                for sr in slot_list:
                    sn = sr["slot"]
                    if role in _REG_SLOT_ROLES:
                        a = sr.get("assigned")
                        if a is None:
                            slot_parts.append(f"{sn}=unused")
                        elif sr["specified"]:
                            slot_parts.append(f"{sn}={a}[locked]")
                        else:
                            slot_parts.append(f"{sn}={a}")
                    elif role in _MEM_SLOT_ROLES:
                        off = sr.get("assigned_offset")
                        if off is None:
                            slot_parts.append(f"{sn}=unused")
                        elif sr["specified"]:
                            slot_parts.append(f"{sn}=mem[{off}][locked]")
                        else:
                            slot_parts.append(f"{sn}=mem[{off}]")

            cond_str = (f" cond={rec['condition_assigned']}"
                        if "condition_assigned" in rec else "")
            ba = rec.get("branch_annotations")
            btb_str = (f" [btb={ba['btb_prediction']} btb_pc={ba['btb_predicted_pc']}]"
                       if ba else "")

            lines.append(
                f"{rec['pc']:04d} {rec['instruction']:12s} "
                f"{rec['kind']}->{rec.get('concrete_instruction', '?'):12s} "
                f"resolved={str(rec['resolved']).lower()} "
                f"committed={str(rec['committed']).lower()}"
                + cond_str + " "
                + " ".join(slot_parts)
                + btb_str
            )

        lines.append("")
        lines.append(f"locked_register_count={n_locked_regs}")
        lines.append(f"locked_memory_count={n_locked_mems}")
        lines.append(f"alloca_total_bytes={alloca_total_bytes}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return result


# =============================================================================
# Pass 4: SSA renaming
# =============================================================================

# Slot names that define a new value (writes).  Only outreg ever writes a
# register-typed SSA value; outmem writes to memory which has no SSA value.
_SSA_WRITE_SLOT_NAMES: Set[str] = {"outreg"}

# Slot names that consume an existing value (reads).
_SSA_READ_SLOT_NAMES: Set[str] = {"inreg0", "inreg1", "inaddr"}


def pass4_ssa(
    pass3_result: Dict[str, Any],
    out_path: Optional[str] = None,
    write_out: bool = False,
) -> Dict[str, Any]:
    """
    Pass 4: assign SSA names to every active register slot.

    Strategy
    --------
    Walk instructions in PC order (already topologically sorted by spo).
    For each instruction:
      1. Record SSA names for all READ slots (inreg0, inreg1, inaddr) using
         the current version of the assigned register.
      2. Then create a fresh SSA name for the WRITE slot (outreg) and advance
         the current version for that register.

    Reads are resolved before writes so an instruction like  add %x, %x  that
    reads and writes the same virtual register gets the OLD value on both
    inputs and defines a new version on output — correct SSA semantics.

    Memory slots (inmem, outmem) carry byte offsets, not values; they are
    left unchanged (no ssa_name added).

    Slots with assigned=None (not used by the concrete instruction) get
    ssa_name=None and are skipped.

    SSA name format
    ---------------
    "{reg}_{n}"  e.g. rax_1, rx0_0, rx0_1
    Version 0 is the implicit initial value (register read before first write).
    No "%" prefix — the IR emitter prepends it when emitting LLVM IR text.

    Output dict additions
    ---------------------
    result["ssa_init"]  : Dict[str, str]
        Registers that were read before their first write in program order.
        Maps physical/virtual register name -> its version-0 SSA name.
        The IR emitter must emit an initialization for each of these at the
        start of the function body:
          - locked register  (in locked_registers.values()): set via inline-asm
            output constraint to the desired initial value.
          - virtual register (rx*): emit  %{name} = add i64 0, 0

    Per active register slot dict, a new key is added:
        "ssa_name" : str | None
            The SSA name for this occurrence (read or def).
            None if the slot is unused (assigned=None).

    Branch conditions
    -----------------
    For any instruction with condition_assigned, the following is added:
        instruction["condition_ssa_forced"] : "i1 true" | "i1 false"
    The IR emitter should use this constant directly in the  br i1  operand
    so the condition is not folded away by the compiler before reaching the
    microarchitectural simulator.  The inreg0 ssa_name is still computed for
    bookkeeping (it represents the register the model placed the condition in).
    """
    current: Dict[str, str] = {}   # reg_name -> current SSA name
    counter: Dict[str, int] = {}   # reg_name -> next version number
    init_needed: Dict[str, str] = {}  # reg_name -> version-0 name

    def fresh(reg: str) -> str:
        n = counter.get(reg, 0) + 1
        counter[reg] = n
        name = f"{reg}_{n}"
        current[reg] = name
        return name

    def lookup(reg: str) -> str:
        if reg not in current:
            name = f"{reg}_0"
            current[reg] = name
            init_needed[reg] = name
        return current[reg]

    instructions: List[Dict[str, Any]] = []

    for rec in pass3_result["instructions"]:
        concrete = rec.get("concrete_instruction")
        uses = _uses_for(concrete)

        new_rec = dict(rec)
        new_slots: Dict[str, List[Dict[str, Any]]] = {}

        # Collect write-slot dicts so we can update them after processing reads.
        pending_writes: List[Tuple[Dict[str, Any], str]] = []  # (slot_dict, reg_name)

        for role, slot_list in rec["slots"].items():
            new_slot_list: List[Dict[str, Any]] = []
            for sr in slot_list:
                new_sr = dict(sr)
                slot_name = sr["slot"]
                assigned = sr.get("assigned")  # None if slot not used

                if role in _REG_SLOT_ROLES and slot_name in uses and assigned is not None:
                    if slot_name in _SSA_WRITE_SLOT_NAMES:
                        new_sr["ssa_name"] = None      # filled after reads
                        pending_writes.append((new_sr, assigned))
                    else:
                        new_sr["ssa_name"] = lookup(assigned)   # read
                else:
                    new_sr["ssa_name"] = None          # unused slot

                new_slot_list.append(new_sr)
            new_slots[role] = new_slot_list

        # Now process writes (after all reads have captured their current version)
        for slot_dict, reg_name in pending_writes:
            slot_dict["ssa_name"] = fresh(reg_name)

        new_rec["slots"] = new_slots

        # Branch: propagate forced condition constant for the IR emitter
        if rec.get("condition_assigned") is not None:
            new_rec["condition_ssa_forced"] = (
                "i1 true" if rec["condition_assigned"] else "i1 false"
            )

        instructions.append(new_rec)

    result: Dict[str, Any] = {
        "instructions": instructions,
        "resource_usage": pass3_result["resource_usage"],
        "branch_mode": pass3_result.get("branch_mode"),
        "needs_end_block": pass3_result.get("needs_end_block", False),
        "locked_registers": pass3_result["locked_registers"],
        "virtual_reg_pool": pass3_result["virtual_reg_pool"],
        "memory_offsets": pass3_result["memory_offsets"],
        "alloca_total_bytes": pass3_result["alloca_total_bytes"],
        "alloca_total_slots": pass3_result["alloca_total_slots"],
        "ssa_init": init_needed,
    }

    if write_out:
        if out_path is None:
            raise ValueError("out_path must not be None when write_out=True")
        phys_regs = set(pass3_result["locked_registers"].values())
        lines = ["# SPO Abstract Program (phase 4 - SSA)"]
        lines.append(f"# locked_registers : {pass3_result['locked_registers']}")
        lines.append(f"# ssa_init         : {init_needed}")
        lines.append(f"# alloca           : {pass3_result['alloca_total_slots']} x i64 "
                     f"({pass3_result['alloca_total_bytes']} bytes)")
        lines.append("")
        for rec in instructions:
            slot_parts: List[str] = []
            for role, slot_list in rec["slots"].items():
                for sr in slot_list:
                    sn = sr["slot"]
                    if role in _REG_SLOT_ROLES:
                        ssa = sr.get("ssa_name")
                        if ssa is None:
                            slot_parts.append(f"{sn}=-")
                        elif sr["specified"]:
                            slot_parts.append(f"{sn}={ssa}[locked]")
                        else:
                            slot_parts.append(f"{sn}={ssa}")
                    elif role in _MEM_SLOT_ROLES:
                        off = sr.get("assigned_offset")
                        if off is None:
                            slot_parts.append(f"{sn}=-")
                        elif sr["specified"]:
                            slot_parts.append(f"{sn}=mem[{off}][locked]")
                        else:
                            slot_parts.append(f"{sn}=mem[{off}]")

            cond_str = (f" cond_forced={rec['condition_ssa_forced']}"
                        if "condition_ssa_forced" in rec else "")
            ba = rec.get("branch_annotations")
            btb_str = (f" [btb={ba['btb_prediction']} btb_pc={ba['btb_predicted_pc']}]"
                       if ba else "")

            lines.append(
                f"{rec['pc']:04d} {rec['instruction']:12s} "
                f"{rec['kind']}->{rec.get('concrete_instruction', '?'):12s} "
                f"resolved={str(rec['resolved']).lower()} "
                f"committed={str(rec['committed']).lower()}"
                + cond_str + "  "
                + "  ".join(slot_parts)
                + btb_str
            )

        lines.append("")
        lines.append(f"ssa_init: {init_needed}")
        lines.append(f"locked_register_count={len(pass3_result['locked_registers'])}")
        lines.append(f"locked_memory_count={len(pass3_result['memory_offsets'])}")
        lines.append(f"alloca_total_bytes={pass3_result['alloca_total_bytes']}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return result


# =============================================================================
# Pass 5: emit LLVM IR
# =============================================================================

def pass5_emit_llvm(
    pass4_result: Dict[str, Any],
    func_name: str = "test",
    out_path: Optional[str] = None,
    write_out: bool = False,
) -> str:
    """
    Pass 5: emit LLVM IR from the SSA-annotated program.

    Produces a single-function LLVM IR module  @{func_name}() -> i64.

    Memory
    ------
    A single  [N x i64]  alloca covers all memory slots.  Each slot is
    zero-initialised with a volatile store.  Load and store instructions
    address slots via getelementptr; the slot index is
    inmem/outmem "assigned_offset" divided by 8.

    Registers
    ---------
    Registers in ssa_init (read before first write) are zero-initialised
    in the entry block:
      locked (physical x86): inline asm  "movq $1, $0"  with  "={phys},r"
      virtual (rx*):         %name = add i64 0, 0

    Write slots (outreg) on locked physical registers are forced via inline
    asm  "movq $1, $0"  with  "={phys},r"  after computing the result into
    a temporary SSA value.

    Basic blocks
    ------------
    Mispredicted branches emit  br i1 {condition_ssa_forced}, ...
    and create a new bb_{pc} label for the fallthrough successor.
    All branches that target end_block cause  end_block: ret i64 0  to be
    appended at the end of the function.

    Resolved branches are emitted as a comment (no-op in the linear flow).
    """
    instructions = pass4_result["instructions"]
    locked_registers: Dict[str, str] = pass4_result["locked_registers"]
    ssa_init: Dict[str, str] = pass4_result["ssa_init"]
    alloca_n: int = pass4_result["alloca_total_slots"]
    needs_end_block: bool = pass4_result.get("needs_end_block", False)

    # PCs that start new basic blocks (fallthrough targets of mispredicted branches)
    new_block_pcs: Set[int] = set()
    for rec in instructions:
        ba = rec.get("branch_annotations")
        if ba:
            ft = ba.get("fallthrough_target", "")
            if ft.startswith("bb_"):
                try:
                    new_block_pcs.add(int(ft[3:]))
                except ValueError:
                    pass

    # ---- Slot helpers ----
    def get_slot(rec: Dict[str, Any], slot_name: str) -> Optional[Dict[str, Any]]:
        for slot_list in rec["slots"].values():
            for sr in slot_list:
                if sr["slot"] == slot_name:
                    return sr
        return None

    def ssa_ref(rec: Dict[str, Any], slot_name: str) -> Optional[str]:
        """Return %ssa_name for the given slot, or None if unused."""
        sr = get_slot(rec, slot_name)
        if sr is None:
            return None
        name = sr.get("ssa_name")
        return f"%{name}" if name else None

    def mem_slot_idx(rec: Dict[str, Any], slot_name: str) -> Optional[int]:
        """Return i64 array slot index (assigned_offset // 8) for a memory slot."""
        sr = get_slot(rec, slot_name)
        if sr is None:
            return None
        off = sr.get("assigned_offset")
        return off // 8 if off is not None else None

    # Unique-name generator for anonymous temporaries
    _ctr: Dict[str, int] = {}

    def tmp(tag: str = "t") -> str:
        _ctr[tag] = _ctr.get(tag, 0) + 1
        return f"%__{tag}_{_ctr[tag]}"

    # ---- Emit helpers ----
    lines: List[str] = []
    I = "  "

    def il(s: str) -> None:
        lines.append(I + s)

    def lbl(name: str) -> None:
        lines.append(f"{name}:")

    def cm(s: str) -> None:
        il(f"; {s}")

    def asm_force(ssa_name: str, phys: str, val: str) -> None:
        """Force `val` (SSA ref or i64 constant) into the physical register `phys`."""
        il(f'%{ssa_name} = call i64 asm sideeffect "movq $1, $0", "={{{phys}}},r"(i64 {val})')

    # ---- Function header ----
    lines.append(f"define i64 @{func_name}() {{")
    lbl("entry")

    # ---- Detect inaddr uses: need a probe array as base ----
    # When inaddr is specified, the secret value is used as an OFFSET into probe_mem
    # (not the raw base address). This is the canonical Spectre pattern:
    #   movq (%probe_base, %secret, 1), %dst
    # Different secret values hit different cache lines → observable side channel.
    # probe_mem is always valid; secret=0 just reads probe_mem[0].
    _has_inaddr_load_or_store = any(
        (get_slot(_r, "inaddr") or {}).get("specified") and
        (get_slot(_r, "inaddr") or {}).get("ssa_name")
        for _r in instructions
        if _r.get("concrete_instruction") in ("load", "store")
    )

    # ---- Alloca + memory zero-initialisation ----
    if alloca_n > 0:
        il(f"%mem_base = alloca [{alloca_n} x i64], align 8")
        for i in range(alloca_n):
            gp = tmp("mg")
            il(f"{gp} = getelementptr [{alloca_n} x i64], ptr %mem_base, i64 0, i64 {i}")
            il(f"store volatile i64 0, ptr {gp}, align 8")

    # ---- Probe array for inaddr-based loads/stores ----
    # 256 slots × 64 bytes (cache-line stride) = one cache line per possible byte value.
    if _has_inaddr_load_or_store:
        il(f"%probe_mem = alloca [256 x i64], align 64")
        for _pi in range(256):
            _pgp = tmp("pg")
            il(f"{_pgp} = getelementptr [256 x i64], ptr %probe_mem, i64 0, i64 {_pi}")
            il(f"store volatile i64 0, ptr {_pgp}, align 8")

    # ---- SSA init: zero-initialise registers read before first write ----
    for reg, ssa_name in sorted(ssa_init.items()):
        asm_force(ssa_name, reg, "0")

    # ---- Condition slots for mispredicted branches ----
    # For each mispredict_not_taken branch, allocate a cache-line-aligned slot
    # and initialise it to 1 (so the branch condition resolves to "taken").
    # The slot is flushed from cache at the branch site to maximise the
    # speculation window (the load will miss L1/L2/L3, ~200-300 cycles).
    cond_slots: Dict[int, str] = {}
    for rec in instructions:
        ba = rec.get("branch_annotations")
        if ba and ba.get("mode") == "mispredict_not_taken":
            slot = f"%cond_slot_pc{rec['pc']}"
            # align 64 = cache-line aligned so clflush hits exactly this line
            il(f"{slot} = alloca i64, align 64")
            il(f"store volatile i64 1, ptr {slot}, align 64")
            cond_slots[rec["pc"]] = slot

    # ---- Commit boundary PCs ----
    last_committed_pc: Optional[int] = None
    first_noncommitted_pc: Optional[int] = None
    for rec in instructions:
        if rec.get("committed", False):
            last_committed_pc = rec["pc"]
    for rec in instructions:
        if not rec.get("committed", False):
            first_noncommitted_pc = rec["pc"]
            break

    # ---- Emit instructions ----
    last_was_terminator = False
    safe_name = func_name.replace("-", "_").replace(".", "_")

    for rec in instructions:
        pc = rec["pc"]
        concrete = rec.get("concrete_instruction")
        atom = rec["instruction"]

        if pc in new_block_pcs:
            lbl(f"bb_{pc}")

        cm(f"pc={pc}  {atom}  ({concrete})")
        marker = f"__litmus_{safe_name}_pc{pc}"
        # pc marker prefix shared by all asm blocks below; each instruction
        # type integrates it into its own single asm sideeffect call so that
        # nothing (GEP, icmp, etc.) can appear between the label and the
        # actual instruction in the compiled output.
        mkr = f".globl {marker}\\0A{marker}:\\0A"
        if pc == last_committed_pc:
            cb = f"__litmus_{safe_name}_last_committed"
            mkr += f".globl {cb}\\0A{cb}:\\0A"
        if pc == first_noncommitted_pc:
            cb = f"__litmus_{safe_name}_first_noncommitted"
            mkr += f".globl {cb}\\0A{cb}:\\0A"

        last_was_terminator = False

        if concrete == "load":
            inaddr_sr = get_slot(rec, "inaddr")
            # Only use the rf-specified inaddr — virtual-pool assignments are noise
            _ia_specified = inaddr_sr and inaddr_sr.get("specified")
            inaddr_ssa  = inaddr_sr.get("ssa_name") if _ia_specified else None
            inaddr_phys = inaddr_sr.get("assigned") if _ia_specified else None
            outreg_sr = get_slot(rec, "outreg")
            if inaddr_ssa and inaddr_phys:
                # Secret value used as byte offset into probe_mem — canonical Spectre pattern:
                #   movq (%probe_mem, %secret, 1), %dst
                # probe_mem is always valid; different secret values hit different cache lines.
                if outreg_sr and outreg_sr.get("ssa_name"):
                    out_name = outreg_sr["ssa_name"]
                    phys = outreg_sr.get("assigned")
                    il(f'%{out_name} = call i64 asm sideeffect '
                       f'"{mkr}movq ($1, $2, 1), $0", '
                       f'"=&{{{phys}}},r,{{{inaddr_phys}}},~{{memory}}"'
                       f'(ptr %probe_mem, i64 %{inaddr_ssa})')
                else:
                    il(f'call void asm sideeffect '
                       f'"{mkr}movq ($0, $1, 1), %%rax", '
                       f'"r,{{{inaddr_phys}}},~{{memory}},~{{rax}}"'
                       f'(ptr %probe_mem, i64 %{inaddr_ssa})')
            else:
                idx = mem_slot_idx(rec, "inmem")
                if idx is None or alloca_n == 0:
                    il(f'call void asm sideeffect ".globl {marker}\\0A{marker}:", ""()')
                    cm(f"WARNING: load {atom} missing inmem offset — skipped")
                    continue
                offset = idx * 8
                if outreg_sr and outreg_sr.get("ssa_name"):
                    out_name = outreg_sr["ssa_name"]
                    phys = outreg_sr.get("assigned")
                    il(f'%{out_name} = call i64 asm sideeffect '
                       f'"{mkr}movq {offset}($1), $0", '
                       f'"=&{{{phys}}},r,~{{memory}}"(ptr %mem_base)')
                else:
                    il(f'call void asm sideeffect '
                       f'"{mkr}movq {offset}($0), %rax", '
                       f'"r,~{{memory}},~{{rax}}"(ptr %mem_base)')

        elif concrete == "store":
            inaddr_sr = get_slot(rec, "inaddr")
            _ia_specified = inaddr_sr and inaddr_sr.get("specified")
            inaddr_ssa  = inaddr_sr.get("ssa_name") if _ia_specified else None
            inaddr_phys = inaddr_sr.get("assigned") if _ia_specified else None
            inreg0_sr = get_slot(rec, "inreg0")
            if inaddr_ssa and inaddr_phys:
                # Address comes from register via rf edge — use it directly
                # Secret value as byte offset into probe_mem (store to tagged cache line)
                if inreg0_sr and inreg0_sr.get("ssa_name"):
                    src_ssa = f'%{inreg0_sr["ssa_name"]}'
                    phys_src = inreg0_sr.get("assigned")
                    in_con = f'{{{phys_src}}}' if phys_src else 'r'
                    il(f'call void asm sideeffect '
                       f'"{mkr}movq $0, ($1, $2, 1)", '
                       f'"{in_con},r,{{{inaddr_phys}}},~{{memory}}"'
                       f'(i64 {src_ssa}, ptr %probe_mem, i64 %{inaddr_ssa})')
                else:
                    il(f'call void asm sideeffect '
                       f'"{mkr}movq $$0, ($0, $1, 1)", '
                       f'"r,{{{inaddr_phys}}},~{{memory}}"'
                       f'(ptr %probe_mem, i64 %{inaddr_ssa})')
            else:
                idx = mem_slot_idx(rec, "outmem")
                if idx is None or alloca_n == 0:
                    il(f'call void asm sideeffect ".globl {marker}\\0A{marker}:", ""()')
                    cm(f"WARNING: store {atom} missing outmem offset — skipped")
                    continue
                offset = idx * 8
                if inreg0_sr and inreg0_sr.get("ssa_name"):
                    src_ssa = f'%{inreg0_sr["ssa_name"]}'
                    phys_src = inreg0_sr.get("assigned")
                    in_con = f'{{{phys_src}}}' if phys_src else 'r'
                    il(f'call void asm sideeffect '
                       f'"{mkr}movq $0, {offset}($1)", '
                       f'"{in_con},r,~{{memory}}"(i64 {src_ssa}, ptr %mem_base)')
                else:
                    il(f'call void asm sideeffect '
                       f'"{mkr}movq $$0, {offset}($0)", '
                       f'"r,~{{memory}}"(ptr %mem_base)')

        elif concrete == "bitnot":
            inreg0 = ssa_ref(rec, "inreg0") or "0"
            inreg0_sr = get_slot(rec, "inreg0")
            phys_in = inreg0_sr.get("assigned") if inreg0_sr else None
            outreg_sr = get_slot(rec, "outreg")
            if outreg_sr and outreg_sr.get("ssa_name"):
                out_name = outreg_sr["ssa_name"]
                phys_out = outreg_sr.get("assigned")
                if phys_in and phys_in == phys_out:
                    # same register: NOT in place
                    il(f'%{out_name} = call i64 asm sideeffect '
                       f'"{mkr}notq $0", '
                       f'"=&{{{phys_out}}},0,~{{flags}}"(i64 {inreg0})')
                else:
                    in_con = f'{{{phys_in}}}' if phys_in else 'r'
                    il(f'%{out_name} = call i64 asm sideeffect '
                       f'"{mkr}movq $1, $0\\0Anotq $0", '
                       f'"=&{{{phys_out}}},{in_con},~{{flags}}"(i64 {inreg0})')
            else:
                in_con = f'{{{phys_in}}}' if phys_in else 'r'
                il(f'call void asm sideeffect '
                   f'"{mkr}notq $0", '
                   f'"{in_con},~{{flags}}"(i64 {inreg0})')

        elif concrete == "add":
            inreg0 = ssa_ref(rec, "inreg0") or "0"
            inreg1 = ssa_ref(rec, "inreg1") or "0"
            inreg0_sr = get_slot(rec, "inreg0")
            inreg1_sr = get_slot(rec, "inreg1")
            phys_in0 = inreg0_sr.get("assigned") if inreg0_sr else None
            phys_in1 = inreg1_sr.get("assigned") if inreg1_sr else None
            outreg_sr = get_slot(rec, "outreg")
            if outreg_sr and outreg_sr.get("ssa_name"):
                out_name = outreg_sr["ssa_name"]
                phys_out = outreg_sr.get("assigned")
                in0_con = f'{{{phys_in0}}}' if phys_in0 else 'r'
                in1_con = f'{{{phys_in1}}}' if phys_in1 else 'r'
                il(f'%{out_name} = call i64 asm sideeffect '
                   f'"{mkr}leaq ($1, $2), $0", '
                   f'"=&{{{phys_out}}},{in0_con},{in1_con}"(i64 {inreg0}, i64 {inreg1})')
            else:
                in0_con = f'{{{phys_in0}}}' if phys_in0 else 'r'
                in1_con = f'{{{phys_in1}}}' if phys_in1 else 'r'
                il(f'call void asm sideeffect '
                   f'"{mkr}leaq ($0, $1), %rax", '
                   f'"{in0_con},{in1_con},~{{rax}}"(i64 {inreg0}, i64 {inreg1})')

        elif concrete in ("br_cond", "br_uncond"):
            ba = rec.get("branch_annotations")
            if ba:
                taken = ba["taken_target"]
                ft    = ba["fallthrough_target"]
                cm(f"BTB predicts={ba['btb_prediction']}  btb_predicted_pc={ba['btb_predicted_pc']}")
                if ba.get("mode") == "mispredict_not_taken" and pc in cond_slots:
                    # Use virtual pool registers for ALL branch machinery so the
                    # compiler never touches locked test registers (no spill).
                    # scratch  = cond_slot pointer (for clflush)
                    # cond_reg = loaded condition value (for compare)
                    slot = cond_slots[pc]
                    vpool = pass4_result.get("virtual_reg_pool", [])
                    scratch  = vpool[0] if len(vpool) > 0 else "r10"
                    cond_reg = vpool[1] if len(vpool) > 1 else "r11"
                    # clflush block — explicit scratch register
                    il(f'call void asm sideeffect '
                       f'"{mkr}mfence\\0Aclflush ($0)\\0Amfence", '
                       f'"{{{scratch}}},~{{memory}}"(ptr {slot})')
                    # Condition load — forced into cond_reg, not a free compiler choice
                    cond_raw = tmp("cond_raw")
                    cond_i1  = tmp("cond_i1")
                    il(f'{cond_raw} = call i64 asm sideeffect '
                       f'"movq ($1), $0", '
                       f'"=&{{{cond_reg}}},{{{scratch}}},~{{memory}}"(ptr {slot})')
                    il(f"{cond_i1} = icmp ne i64 {cond_raw}, 0")
                    il(f"br i1 {cond_i1}, label %{taken}, label %{ft}")
                else:
                    il(f'call void asm sideeffect "{mkr}", ""()')
                    cond = rec.get("condition_ssa_forced", "i1 true")
                    il(f"br {cond}, label %{taken}, label %{ft}")
                last_was_terminator = True
            else:
                # Resolved branch: emit marker only, no branch instruction
                il(f'call void asm sideeffect "{mkr}", ""()')
                cm(f"resolved branch {atom} — skipped")

        else:
            il(f'call void asm sideeffect "{mkr}", ""()')
            cm(f"unknown concrete_instruction={concrete!r} — skipped")

    # ---- Epilogue ----
    if needs_end_block:
        if not last_was_terminator:
            il("br label %end_block")
        lbl("end_block")
        il("ret i64 0")
    else:
        if not last_was_terminator:
            il("ret i64 0")

    lines.append("}")
    ir = "\n".join(lines)

    if write_out:
        if out_path is None:
            raise ValueError("out_path must not be None when write_out=True")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(ir + "\n")

    return ir


# =============================================================================
# Branch annotation emitter (side output, callable on any result >= pass 2.5)
# =============================================================================

def emit_branch_annotations(
    result: Dict[str, Any],
    out_path: Optional[str] = None,
    write_out: bool = False,
) -> List[Dict[str, Any]]:
    """
    Collect the BTB force annotations for every unresolved branch.

    For each instruction that has branch_annotations, records:
      branch_pc           : int  — PC (instruction index) of the branch
      branch_atom         : str  — Alloy atom name (e.g. "Branchx$0")
      btb_forced_target_pc: int  — the PC the simulator should force the BTB
                                   to predict as the next instruction.
                                   This is the wrong target; speculative
                                   execution proceeds from this PC.
      mode                : str  — misprediction mode (e.g. "mispredict_not_taken")

    Returns a list of annotation dicts (one per unresolved branch, in PC order).

    If write_out=True, writes a JSON file to out_path with the structure:
      {
        "branch_mode": str,
        "annotations": [ { branch_pc, branch_atom, btb_forced_target_pc, mode }, ... ]
      }

    The btb_forced_target_pc is a PC index into the instruction sequence (0-based).
    The simulator is responsible for resolving this to an actual memory address at
    load time (e.g. by looking up the address of the instruction at that index).
    """
    import json

    annotations: List[Dict[str, Any]] = []

    for rec in result["instructions"]:
        ba = rec.get("branch_annotations")
        if ba is None:
            continue
        annotations.append({
            "branch_pc":            rec["pc"],
            "branch_atom":          rec["instruction"],
            "btb_forced_target_pc": ba["btb_predicted_pc"],
            "mode":                 ba["mode"],
        })

    # Collect xmit instruction (flagged by isxm in the Alloy model).
    # There is at most one per instance (fact one_xm).
    xmit = None
    for rec in result["instructions"]:
        if rec.get("xm", False):
            xmit = {
                "pc":   rec["pc"],
                "kind": rec["kind"],
                "atom": rec["instruction"],
            }
            break

    # Collect commit boundary (last committed / first noncommitted instruction).
    last_committed: Optional[Dict[str, Any]] = None
    first_noncommitted: Optional[Dict[str, Any]] = None
    for rec in result["instructions"]:
        if rec.get("committed", False):
            last_committed = {"pc": rec["pc"], "atom": rec["instruction"]}
    for rec in result["instructions"]:
        if not rec.get("committed", False):
            first_noncommitted = {"pc": rec["pc"], "atom": rec["instruction"]}
            break

    if write_out:
        if out_path is None:
            raise ValueError("out_path must not be None when write_out=True")
        payload: Dict[str, Any] = {
            "branch_mode": result.get("branch_mode", "unknown"),
            "annotations": annotations,
        }
        if xmit is not None:
            payload["xmit"] = xmit
        cb_payload: Dict[str, Any] = {}
        if last_committed is not None:
            cb_payload["last_committed"] = last_committed
        if first_noncommitted is not None:
            cb_payload["first_noncommitted"] = first_noncommitted
        if cb_payload:
            payload["commit_boundary"] = cb_payload
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")

    return annotations


if __name__ == "__main__":
    xml_text = open("alloy-out/STT_new/inst-000001.xml", "r", encoding="utf-8").read()
    inst = parse_alloy_xml(xml_text)
    print(pass1_specify_state_a(inst, out_path="alloy-out/spo_program.ir", write_out=True))