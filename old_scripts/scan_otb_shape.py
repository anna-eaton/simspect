#!/usr/bin/env python3
"""Scan unmodified-Alloy STT_6 xml instances for the OTB chain shape:

    br_resolved -> br_mispredict -> ld1 -> other_n -> ld2(xmit)

with rf edges  ld1.outreg -> other_n.inreg  and  other_n.outreg -> ld2.inaddr,
and ld2 tagged as the xmit transmitter.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "STAGE2_compilation"))
from parsexml import parse_alloy_xml


def kind_atom_for(inst, label):
    """Return the single atom of a one-sig like 'this/TLoad'."""
    atoms = inst.sig_atoms.get(label, set())
    return next(iter(atoms)) if atoms else None


def matches_otb_shape(inst) -> bool:
    instr_set = inst.sig_atoms.get("this/Instruction", set())
    if not instr_set:
        return False

    # kind atoms
    t_load    = kind_atom_for(inst, "this/TLoad")
    t_othern  = kind_atom_for(inst, "this/TOthern")
    t_branchn = kind_atom_for(inst, "this/TBranchn")
    t_branchx = kind_atom_for(inst, "this/TBranchx")
    branch_kinds = {k for k in (t_branchn, t_branchx) if k}

    # instr -> kind atom
    kind_field = inst.fields.get("kind", [])
    instr_kind = {t[0]: t[1] for t in kind_field}

    loads    = {i for i, k in instr_kind.items() if k == t_load}
    others_n = {i for i, k in instr_kind.items() if k == t_othern}
    branches = {i for i, k in instr_kind.items() if k in branch_kinds}

    if len(loads) < 2 or not others_n or len(branches) < 2:
        return False

    # spo:  instr -> instr (next in program order)
    spo_field = inst.fields.get("spo", [])
    succ = {}
    for a, b in spo_field:
        succ.setdefault(a, set()).add(b)
    # Transitive closure of spo (small — only 6 instrs)
    def reaches(a, b):
        seen = {a}
        stack = [a]
        while stack:
            x = stack.pop()
            for y in succ.get(x, ()):
                if y == b:
                    return True
                if y not in seen:
                    seen.add(y); stack.append(y)
        return False

    # resolved set: instr atom whose isresolved tuple holds rBool$0
    resolved = {t[0] for t in inst.fields.get("isresolved", [])}

    # xm set: instr atom whose isxm holds tBool$0
    xm = {t[0] for t in inst.fields.get("isxm", [])}

    # operand → instr (via inverse of each operand-relation)
    def op_owner_map():
        m = {}
        for fname in ("inreg", "inaddr", "inmem", "outreg", "outmem"):
            for t in inst.fields.get(fname, []):
                # tuple is (instr, operand)
                m.setdefault(t[1], set()).add(t[0])
        return m

    inreg_of  = {}
    outreg_of = {}
    inaddr_of = {}
    for t in inst.fields.get("inreg", []):  inreg_of.setdefault(t[0], set()).add(t[1])
    for t in inst.fields.get("outreg", []): outreg_of.setdefault(t[0], set()).add(t[1])
    for t in inst.fields.get("inaddr", []): inaddr_of.setdefault(t[0], set()).add(t[1])

    # rf:  source_operand -> dest_operand
    rf_dest = {}
    for s, d in inst.fields.get("rf", []):
        rf_dest.setdefault(s, set()).add(d)

    # Search: pick b1, b2, ld1, om, ld2 satisfying the shape
    for b1 in branches:
        if b1 not in resolved:
            continue
        for b2 in branches:
            if b2 == b1 or b2 in resolved:
                continue
            if not reaches(b1, b2):
                continue
            for ld1 in loads:
                if not reaches(b2, ld1):
                    continue
                for om in others_n:
                    if not reaches(ld1, om):
                        continue
                    for ld2 in loads:
                        if ld2 == ld1 or not reaches(om, ld2):
                            continue
                        if ld2 not in xm:
                            continue
                        # rf: ld1.outreg -> om.inreg
                        rf_ld1_targets = set()
                        for o in outreg_of.get(ld1, ()):
                            rf_ld1_targets |= rf_dest.get(o, set())
                        if not (rf_ld1_targets & inreg_of.get(om, set())):
                            continue
                        # rf: om.outreg -> ld2.inaddr
                        rf_om_targets = set()
                        for o in outreg_of.get(om, ()):
                            rf_om_targets |= rf_dest.get(o, set())
                        if not (rf_om_targets & inaddr_of.get(ld2, set())):
                            continue
                        return True
    return False


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: scan_otb_shape.py <xml_dir> [limit]")
    xdir = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9

    files = sorted(f for f in os.listdir(xdir) if f.endswith(".xml"))[:limit]
    n = 0; hits = 0; samples = []
    for f in files:
        with open(os.path.join(xdir, f)) as fp:
            inst = parse_alloy_xml(fp.read())
        n += 1
        if matches_otb_shape(inst):
            hits += 1
            if len(samples) < 5:
                samples.append(f)
        if n % 5000 == 0:
            print(f"  scanned {n:>6d}  hits so far: {hits}")
    pct = hits/n*100 if n else 0
    print(f"\nScanned {n} xml instances")
    print(f"OTB-shape matches: {hits}  ({pct:.2f}%)")
    print("First samples:", samples)


if __name__ == "__main__":
    main()
