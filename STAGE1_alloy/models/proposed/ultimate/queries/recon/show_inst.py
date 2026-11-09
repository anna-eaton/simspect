#!/usr/bin/env python3
"""show_inst.py -- print Alloy instances (a6CountModels XML) of the ReCon/STT models as programs and tag ReCon shapes.
Usage: python3 -I show_inst.py <inst.xml | dir-of-inst-xml> [--max N] [--summary]
Per instruction (spo order): position, kind, R/u (resolved), C/- (committed), XM, operands as role:state,
rf sources. Shape tags (unperturbed program, no_p), computed here independently of Alloy:
  pairC / pairU  direct load pair LD1 -> LD2 (LD1.outreg rf-feeds LD2.inaddr), LD2 committed / uncommitted
  reread         a speculative load (uncommitted, after an unresolved branch) reads the word of a pair's LD1 later
  conceal(res|unres)  a store to that word sits between LD1 and the re-load (address resolved / unresolved)
  alu_pair       LD1 -> ALU -> LD2 (committed), the near-miss that is NOT a direct pair
  R1             a non-speculative load and a later speculative load read the same word (audit R-1 shape)
  alu_xm         an ALU op's output feeds the transmitter's leak operand (OTB precursor)
  d2             pairU whose LD2 is the first uncommitted instruction and whose LD1 word is re-read
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def strip(a):
    return a.split("$")[0] + "$" + a.split("$")[1] if "$" in a else a


def load(path):
    root = ET.parse(path).getroot()
    inst = root.find("instance")
    fields = {}
    for f in inst.findall("field"):
        rows = [tuple(a.get("label") for a in t.findall("atom")) for t in f.findall("tuple")]
        fields.setdefault(f.get("label"), []).extend(rows)
    sigs = {}
    for s in inst.findall("sig"):
        sigs[s.get("label")] = [a.get("label") for a in s.findall("atom")]
    return fields, sigs


def analyse(path):
    F, S = load(path)
    I = S.get("this/Instruction", [])
    kind = {a: b.split("$")[0][1:] for a, b in F.get("kind", [])}
    spo = dict(F.get("spo", []))
    first = [i for i in I if i not in spo.values()]
    order = []
    cur = first[0] if first else None
    while cur is not None and cur not in order:
        order.append(cur)
        cur = spo.get(cur)
    pos = {i: n for n, i in enumerate(order)}
    res = {a for a, _ in F.get("isresolved", [])}
    com = {a for a, _ in F.get("iscommitted", [])}
    xm = {a for a, _ in F.get("isxm", [])}
    ops = {}
    for role in ("inreg", "inaddr", "outreg", "inmem", "outmem"):
        for a, o in F.get(role, []):
            ops.setdefault(a, []).append((role, o))
    owner = {o: a for a, l in ops.items() for _, o in l}
    st = dict(F.get("opstate", []))
    rf = F.get("rf", [])
    ddi = set(F.get("ddi", []))
    rf_in = {c: p for p, c in rf}
    br = [i for i in order if kind[i] in ("Branchn", "Branchx")]
    unres_br = [b for b in br if b not in res]

    def spec(i):
        return i not in com and any(pos[b] < pos[i] for b in unres_br)

    def of(i, role):
        return [o for r, o in ops.get(i, []) if r == role]

    loads = [i for i in order if kind[i] == "Load"]
    stores = [i for i in order if kind[i] == "Store"]
    pairs = []
    for l1 in loads:
        for l2 in loads:
            if any((o1, o2) in set(rf) for o1 in of(l1, "outreg") for o2 in of(l2, "inaddr")):
                pairs.append((l1, l2))
    tags = set()
    fu = next((i for i in order if i not in com), None)
    for l1, l2 in pairs:
        tags.add("pairC" if l2 in com else "pairU")
        w = [st[o] for o in of(l1, "inmem")]
        for l3 in loads:
            if spec(l3) and pos[l3] > pos[l1] and w and any(st[o] in w for o in of(l3, "inmem")):
                tags.add("reread")
                if l2 not in com and l2 == fu:
                    tags.add("d2")
                for s in stores:
                    if pos[l1] < pos[s] < pos[l3] and any(st[o] in w for o in of(s, "outmem")):
                        tags.add("conceal(res)" if (s in res or s in com) else "conceal(unres)")
    for l1 in loads:
        for o in [i for i in order if kind[i] in ("Othern", "Otherx")]:
            for l2 in loads:
                if l2 in com and any((a, b) in set(rf) for a in of(l1, "outreg") for b in of(o, "inreg")) and \
                        any((a, b) in set(rf) for a in of(o, "outreg") for b in of(l2, "inaddr")):
                    tags.add("alu_pair")
    for l1 in loads:
        for l3 in loads:
            if not spec(l1) and spec(l3) and pos[l1] < pos[l3] and \
                    {st[o] for o in of(l1, "inmem")} & {st[o] for o in of(l3, "inmem")}:
                tags.add("R1")
    for x in xm:
        leak = of(x, "inaddr") + (of(x, "inreg") if kind[x] == "Branchx" else [])
        for o in leak:
            p = rf_in.get(o)
            if p and kind[owner[p]] in ("Othern", "Otherx"):
                tags.add("alu_xm")
    lines = []
    for i in order:
        rs = " ".join(f"{r}:{st[o].replace('_s', '')}" + (f"<-{pos[owner[rf_in[o]]]}" if o in rf_in else "")
                      for r, o in ops.get(i, []))
        lines.append(f"  {pos[i]} {kind[i]:<7} {'R' if i in res else 'u'}{'C' if i in com else '-'}"
                     f"{' XM' if i in xm else '   '} {rs}")
    return lines, sorted(tags)


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10**9
    summary = "--summary" in sys.argv
    p = Path(a[0])
    files = sorted(p.glob("inst-*.xml")) if p.is_dir() else [p]
    counts = {}
    for n, f in enumerate(files):
        lines, tags = analyse(f)
        key = ",".join(tags) or "-"
        counts[key] = counts.get(key, 0) + 1
        if n < mx and not summary:
            print(f"{f.name}: {key}")
            print("\n".join(lines))
    print(f"# {len(files)} instances; shape tags:")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"#   {v:5d}  {k}")


if __name__ == "__main__":
    main()
