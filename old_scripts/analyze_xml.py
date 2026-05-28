#!/usr/bin/env python3
"""
analyze_xml.py — Pretty-print an Alloy XML instance as pseudocode.

Usage:
    python3 analyze_xml.py <inst-XXXXXX.xml> [...]

Operands are resolved through opstate to the actual State element
(Reg_s$N or Mem_s$N) they reference.

Auto-discovers the matching .ann.json from ../ann/<stem>.ann.json.
Pass --ann-dir to override.

Output format (one line per instruction, in program order):
    [idx] instr_type  state_out <- state_in, ...  (flags)  [ann info]

Flags:  r = resolved, c = committed, xm = transmitter (isxm)
Ann:    xmit kind + x86 offset; branch mode + mnemonic per branch.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def load_ann(xml_path):
    p = Path(xml_path)
    candidates = [
        p.parent.parent / "ann" / (p.stem + ".ann.json"),
        p.parent / (p.stem + ".ann.json"),
    ]
    for c in candidates:
        if c.exists():
            try:
                return json.loads(c.read_text())
            except Exception:
                return None
    return None


def parse_instance(xml_path, ann_dir_override=None):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    inst_el = root.find("instance")
    if inst_el is None:
        sys.exit(f"error: no <instance> in {xml_path}")

    # ── sig atoms ────────────────────────────────────────────────────────────
    sig_atoms = {}
    for sig in inst_el.findall("sig"):
        sig_atoms[sig.get("label", "")] = {
            a.get("label") for a in sig.findall("atom")
        }

    # ── field tuples ──────────────────────────────────────────────────────────
    fields = {}
    for field in inst_el.findall("field"):
        pairs = []
        for tup in field.findall("tuple"):
            atoms = [a.get("label") for a in tup.findall("atom")]
            if len(atoms) == 2:
                pairs.append((atoms[0], atoms[1]))
        fields[field.get("label", "")] = pairs

    def field_map(fname):
        return {a: b for a, b in fields.get(fname, [])}

    def field_set(fname):
        return {a for a, _ in fields.get(fname, [])}

    def field_multi(fname):
        d = {}
        for a, b in fields.get(fname, []):
            d.setdefault(a, []).append(b)
        return d

    kind_map   = field_map("kind")
    idx_map    = field_map("idx")
    opstate    = field_map("opstate")   # operand atom → State atom (Reg_s$N / Mem_s$N)
    inreg_map  = field_multi("inreg")
    inaddr_map = field_multi("inaddr")
    outreg_map = field_multi("outreg")
    inmem_map  = field_multi("inmem")
    outmem_map = field_multi("outmem")
    resolved_set  = field_set("isresolved")
    committed_set = field_set("iscommitted")
    xm_set        = field_set("isxm")

    def ix_num(ix_label):
        try:
            return int(ix_label.replace("IX", "").split("$")[0])
        except Exception:
            return 999

    def instr_type(atom):
        return kind_map.get(atom, "?").split("$")[0]

    def resolve_ops(operand_atoms):
        """Map each operand atom through opstate to its State element."""
        return [opstate.get(op, "?") for op in operand_atoms]

    def fmt_ops(operand_atoms):
        states = resolve_ops(operand_atoms)
        return ", ".join(states) if states else "?"

    instructions = sorted(sig_atoms.get("this/Instruction", set()))
    sorted_instrs = sorted(
        instructions, key=lambda a: ix_num(idx_map.get(a, "IX999$0"))
    )

    # ── annotation data ───────────────────────────────────────────────────────
    if ann_dir_override:
        ann_path = Path(ann_dir_override) / (Path(xml_path).stem + ".ann.json")
        ann = json.loads(ann_path.read_text()) if ann_path.exists() else None
    else:
        ann = load_ann(xml_path)

    xmit_note  = {}   # atom → annotation string
    branch_note = {}  # atom → annotation string

    if ann:
        xmit = ann.get("xmit", {})
        if xmit.get("atom"):
            xmit_note[xmit["atom"]] = (
                f"xmit: {xmit.get('kind', '?')}  {xmit.get('x86_offset_hex', '')}"
            )
        for entry in ann.get("annotations", []):
            atom = entry.get("branch_atom")
            if atom:
                branch_note[atom] = (
                    f"{entry.get('mode', '')}  "
                    f"{entry.get('x86_mnemonic', '')}  "
                    f"{entry.get('x86_pc_offset_hex', '')}"
                )

    # ── print ─────────────────────────────────────────────────────────────────
    stem = Path(xml_path).stem
    ann_status = "(ann: found)" if ann else "(ann: not found)"
    print(f"── {stem}  {ann_status} ──")
    print()

    for instr in sorted_instrs:
        pos   = ix_num(idx_map.get(instr, "IX999$0"))
        itype = instr_type(instr)

        out_ops = outreg_map.get(instr, []) + outmem_map.get(instr, [])
        in_ops  = (inreg_map.get(instr, []) + inaddr_map.get(instr, [])
                   + inmem_map.get(instr, []))

        out_str = fmt_ops(out_ops) if out_ops else "?"
        in_str  = fmt_ops(in_ops)  if in_ops  else "?"

        flags = []
        if instr in resolved_set:  flags.append("r")
        if instr in committed_set: flags.append("c")
        if instr in xm_set:        flags.append("xm")
        flag_str = f"  ({', '.join(flags)})" if flags else ""

        ann_parts = []
        if instr in xmit_note:   ann_parts.append(xmit_note[instr])
        if instr in branch_note: ann_parts.append(branch_note[instr])
        ann_str = ("  [" + " | ".join(ann_parts) + "]") if ann_parts else ""

        print(
            f"  [{pos}] {itype:<10}  {out_str:<14} <- {in_str:<20}"
            f"{flag_str}{ann_str}"
        )

    print()


def main():
    args = sys.argv[1:]
    ann_dir = None
    if "--ann-dir" in args:
        i = args.index("--ann-dir")
        ann_dir = args[i + 1]
        args = args[:i] + args[i + 2:]

    if not args:
        sys.exit("usage: python3 analyze_xml.py [--ann-dir <dir>] <inst-*.xml> [...]")

    for path in args:
        parse_instance(path, ann_dir_override=ann_dir)


if __name__ == "__main__":
    main()
