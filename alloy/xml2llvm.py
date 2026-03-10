#!/usr/bin/env python3
"""
alloy_xml_to_llvm.py

Parse an Alloy XML instance (<alloy>...</alloy>),
topo-sort Instructions by `spo`,
build SSA keyed by *physical locations* via Operand.opstate (Reg_s / Mem_s),
and emit straight-line LLVM IR (no branches, no phi).

Key semantic change vs your draft:
- Operand atoms (Inreg$k, Outreg$k, Inmem$k, ...) are instruction-specific.
- Physical identity is Operand.opstate, which points to a State atom that
  represents a single physical location (register slot or memory location).
- Therefore, SSA "registers" are keyed by Reg_s$* atoms, not by operand atoms,
  and memory pointers are keyed by Mem_s$* atoms, not by Inmem$* / Outmem$* atoms.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
import xml.etree.ElementTree as ET


# -----------------------------
# Parse Alloy XML
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
# Toposort
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

    out.reverse()
    return out


# -----------------------------
# LLVM emission helpers
# -----------------------------
def llvm_escape(name: str) -> str:
    return name.replace("$", "_")


def emit_llvm_from_instance(
    inst: AlloyInstance,
    kind_override: Optional[Dict[str, str]] = None,
    op_map: Optional[Dict[str, str]] = None,
    default_const: int = 42,
    ret_policy: str = "last",  # "last" | "reg:R0" | "state:Reg_s$0"
    init_regs_to_zero: bool = True,
) -> str:
    kind_override = kind_override or {}
    op_map = op_map or {}

    # ---- Instruction atoms (adjust if you model more kinds)
    instr_atoms: Set[str] = set()
    for sig_label, atoms in inst.sig_atoms.items():
        if sig_label.startswith("this/") and sig_label.split("/", 1)[1] in {
            "Load", "Store", "Branchn", "Branchx", "Othern", "Otherx"
        }:
            instr_atoms |= atoms
    nodes = sorted(instr_atoms)

    # ---- Program order
    spo_edges = [
        (a, b)
        for (a, b) in inst.fields.get("spo", [])
        if a in instr_atoms and b in instr_atoms
    ]
    order = topo_sort(nodes, spo_edges)

    # ---- Operand relations (Instruction -> Operand)
    # These are operand atoms; physical identity comes from opstate below.
    inreg_t = inst.fields.get("inreg", [])
    outreg_t = inst.fields.get("outreg", [])
    inmem_t = inst.fields.get("inmem", [])
    outmem_t = inst.fields.get("outmem", [])
    inaddr_t = inst.fields.get("inaddr", [])

    inregs_of: Dict[str, List[str]] = {}
    outregs_of: Dict[str, List[str]] = {}
    inmems_of: Dict[str, List[str]] = {}
    outmems_of: Dict[str, List[str]] = {}
    inaddrs_of: Dict[str, List[str]] = {}

    for i, r in inreg_t:
        inregs_of.setdefault(i, []).append(r)
    for i, r in outreg_t:
        outregs_of.setdefault(i, []).append(r)
    for i, m in inmem_t:
        inmems_of.setdefault(i, []).append(m)
    for i, m in outmem_t:
        outmems_of.setdefault(i, []).append(m)
    for i, a in inaddr_t:
        inaddrs_of.setdefault(i, []).append(a)

    # ---- Physical identity: Operand -> State (Reg_s$k / Mem_s$k / ...)
    opstate_t = inst.fields.get("opstate", [])
    opstate_of: Dict[str, str] = {}
    for op, st in opstate_t:
        opstate_of[op] = st

    reg_states = inst.sig_atoms.get("this/Reg_s", set())
    mem_states = inst.sig_atoms.get("this/Mem_s", set())

    def reg_state_of_operand(op: str) -> Optional[str]:
        st = opstate_of.get(op)
        if st in reg_states:
            return st
        return None

    def mem_state_of_operand(op: str) -> Optional[str]:
        st = opstate_of.get(op)
        if st in mem_states:
            return st
        return None

    # ---- Instruction kind inference
    load_atoms = inst.sig_atoms.get("this/Load", set())
    store_atoms = inst.sig_atoms.get("this/Store", set())
    otherx_atoms = inst.sig_atoms.get("this/Otherx", set())
    othern_atoms = inst.sig_atoms.get("this/Othern", set())
    branchn_atoms = inst.sig_atoms.get("this/Branchn", set())
    branchx_atoms = inst.sig_atoms.get("this/Branchx", set())


    def kind_of(ins: str) -> str:
        if ins in kind_override:
            return kind_override[ins]
        if ins in load_atoms:
            return "load"
        if ins in store_atoms:
            return "store"
        if ins in otherx_atoms:
            return "alu_x"
        if ins in othern_atoms:
            return "alu"
        if ins in branchn_atoms:
            return "branch"
        if ins in branchx_atoms:
            return "branch_x"
        return "op"

    # ---- Build the set of physical register locations actually mentioned
    used_reg_states: Set[str] = set()
    for ins in instr_atoms:
        for op in inregs_of.get(ins, []):
            st = reg_state_of_operand(op)
            if st:
                used_reg_states.add(st)
        for op in outregs_of.get(ins, []):
            st = reg_state_of_operand(op)
            if st:
                used_reg_states.add(st)

    # Give stable names R0, R1... based on sorted Reg_s atoms
    reg_state_list = sorted(used_reg_states)
    reg_state_to_name = {st: f"R{idx}" for idx, st in enumerate(reg_state_list)}

    # ---- Build memory pointers keyed by physical Mem_s locations
    used_mem_states: Set[str] = set()
    for ins in instr_atoms:
        for op in inmems_of.get(ins, []):
            st = mem_state_of_operand(op)
            if st:
                used_mem_states.add(st)
        for op in outmems_of.get(ins, []):
            st = mem_state_of_operand(op)
            if st:
                used_mem_states.add(st)

    mem_state_list = sorted(used_mem_states)
    mem_state_to_ptr = {st: f"%mem_{llvm_escape(st)}" for st in mem_state_list}

    # ---- SSA environment keyed by physical register locations (Reg_s)
    cur: Dict[str, str] = {}              # reg_state -> current LLVM SSA value
    ssa_counter: Dict[str, int] = {}      # reg_state -> counter

    def fresh_for_reg_state(reg_st: str) -> str:
        ssa_counter[reg_st] = ssa_counter.get(reg_st, 0) + 1
        rname = reg_state_to_name.get(reg_st, f"R_{llvm_escape(reg_st)}")
        return f"%{rname.lower()}_{ssa_counter[reg_st]}"

    def get_value_from_inreg_operand(inreg_op: str) -> str:
        reg_st = reg_state_of_operand(inreg_op)
        if reg_st is None:
            return "0"
        return cur.get(reg_st, "0")

    def write_to_outreg_operand(outreg_op: str) -> Tuple[str, Optional[str]]:
        reg_st = reg_state_of_operand(outreg_op)
        if reg_st is None:
            return ("%sink_reg_" + llvm_escape(outreg_op), None)
        return (fresh_for_reg_state(reg_st), reg_st)

    # ---- Memory allocation: only for physical Mem_s locations
    lines: List[str] = []
    lines.append("define i64 @test() {")
    lines.append("entry:")

    for st in mem_state_list:
        ptr = mem_state_to_ptr[st]
        lines.append(f"  {ptr} = alloca i64, align 8")
        lines.append(f"  store volatile i64 0, ptr {ptr}, align 8")

    # Optional init regs so reads are defined
    if init_regs_to_zero:
        for st in reg_state_list:
            v = fresh_for_reg_state(st)
            lines.append(f"  {v} = add i64 0, 0")
            cur[st] = v

    last_value: Optional[str] = None

    # Fallback synthetic mem locations if an instruction references a mem operand
    # without a Mem_s opstate (should be rare if model is consistent)
    synth_mem_count = 0

    def synth_mem_ptr() -> str:
        nonlocal synth_mem_count
        name = f"%mem_synth{synth_mem_count}"
        synth_mem_count += 1
        lines.append(f"  {name} = alloca i64, align 8")
        lines.append(f"  store volatile i64 0, ptr {name}, align 8")
        return name

    def pick_mem_ptr_for_operands(mem_ops: List[str]) -> str:
        for op in mem_ops:
            st = mem_state_of_operand(op)
            if st is not None:
                return mem_state_to_ptr.get(st, synth_mem_ptr())
        return synth_mem_ptr()

    # ---- Emit straight-line IR
    for ins in order:
        k = kind_of(ins)
        inr_ops = inregs_of.get(ins, [])
        outr_ops = outregs_of.get(ins, [])
        inm_ops = inmems_of.get(ins, [])
        outm_ops = outmems_of.get(ins, [])

        if k == "load":
            lines.append(f"  ; {ins} (load)")
            # Memory location comes from inmem or outmem operands; both identify a Mem_s location.
            mem_ptr = pick_mem_ptr_for_operands(inm_ops or outm_ops)

            if outr_ops:
                dst, reg_st = write_to_outreg_operand(outr_ops[0])
                lines.append(f"  {dst} = load volatile i64, ptr {mem_ptr}, align 8")
                if reg_st is not None:
                    cur[reg_st] = dst
                last_value = dst
            else:
                sink = f"%sink_{llvm_escape(ins)}"
                lines.append(f"  {sink} = load volatile i64, ptr {mem_ptr}, align 8")
                last_value = sink

        elif k == "store":
            lines.append(f"  ; {ins} (store)")
            src_val = get_value_from_inreg_operand(inr_ops[0]) if inr_ops else str(default_const)

            # Store target is the physical Mem_s location indicated by outmem (preferred) or inmem.
            mem_ptr = pick_mem_ptr_for_operands(outm_ops or inm_ops)
            lines.append(f"  store volatile i64 {src_val}, ptr {mem_ptr}, align 8")
            last_value = src_val

        elif k == "op":
            opcode = op_map.get(ins, "xor")
            lines.append(f"  ; {ins} ({opcode})")

            ops: List[str] = [get_value_from_inreg_operand(op) for op in inr_ops]
            if len(ops) == 0:
                ops = [str(default_const), str(default_const + 1)]
            elif len(ops) == 1:
                ops.append(str(default_const))

            if outr_ops:
                dst, reg_st = write_to_outreg_operand(outr_ops[0])
                lines.append(f"  {dst} = {opcode} i64 {ops[0]}, {ops[1]}")
                if reg_st is not None:
                    cur[reg_st] = dst
                last_value = dst
            else:
                sink = f"%sink_{llvm_escape(ins)}"
                lines.append(f"  {sink} = {opcode} i64 {ops[0]}, {ops[1]}")
                last_value = sink

        else:
            lines.append(f"  ; {ins} (ignored kind={k})")

    # ---- Return policy
    ret_val = "0"
    if ret_policy == "last":
        ret_val = last_value or "0"
    elif ret_policy.startswith("reg:"):
        # reg:R0 style (synthetic names)
        want = ret_policy.split(":", 1)[1].strip()
        # find reg_state whose synthetic name matches
        inv = {v: k for k, v in reg_state_to_name.items()}
        st = inv.get(want)
        if st is not None:
            ret_val = cur.get(st, "0")
    elif ret_policy.startswith("state:"):
        # state:Reg_s$0 style (physical)
        st = ret_policy.split(":", 1)[1].strip()
        ret_val = cur.get(st, "0")

    lines.append(f"  ret i64 {ret_val}")
    lines.append("}")
    return "\n".join(lines)


# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    xml_text = open("alloy-out/STT_new/inst-000001.xml", "r", encoding="utf-8").read()
    inst = parse_alloy_xml(xml_text)

    llvm_ir = emit_llvm_from_instance(
        inst,
        kind_override={},     # optionally override per-instruction: {"Load$0":"load", ...}
        op_map={},            # optionally map ops: {"Otherx$0":"add"}
        default_const=42,
        ret_policy="last",
        init_regs_to_zero=True,
    )
    print(llvm_ir)