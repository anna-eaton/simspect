#!/usr/bin/env python3
"""census.py — shape census of the instances dumped by bench_grid.py (stage15-bound, 2026-11-08).

For each <ws>/bench/dump/<job>/inst-*.txt (Alloy toString dumps): instruction count, operand and
state atoms used, Reg_s atoms (= Stage-2 pass-3 locked registers), unresolved branches, operand-free
branches (pure spacers), and whether an ALU op (Otherns/Otherxs) lies on an rf/ddi path from a
load's output into xm's leak operand (ld/st inaddr, br_x inreg) — "ALU on xm path".

Usage: python3 census.py --ws /tests/stage15_bound_20261108 > census.json
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
import stage_seed  # noqa: E402


def one(path):
    r = stage_seed.parse_txt(str(path))
    kind = {i: k.split("$")[0] for i, k in r.get("Instruction<:kind", [])}
    ins = list(kind)
    res = {i for i, _ in r.get("Instruction<:isresolved", [])}
    xm = [i for i, _ in r.get("Instruction<:isxm", [])]
    ops_of = {}
    for s in ("inreg", "inaddr", "inmem", "outreg", "outmem"):
        for i, o in r.get(f"Instruction<:{s}", []):
            ops_of.setdefault(i, []).append((s, o))
    owner = {o: i for i, l in ops_of.items() for _, o in l}
    states = {st for _, st in r.get("Operand<:opstate", [])}
    regs = {st for st in states if st.startswith("Reg_s")}
    edges = {}
    for a, b in r.get("Operand<:rf", []) + r.get("Operand<:ddi", []):
        edges.setdefault(a, set()).add(b)
    brs = [i for i in ins if kind[i] in ("TBranchn", "TBranchx")]
    alu_on_path = False
    if xm:
        x = xm[0]
        slot = {"TLoad": "inaddr", "TStore": "inaddr", "TBranchx": "inreg"}.get(kind[x])
        targets = {o for s, o in ops_of.get(x, []) if s == slot}
        # BFS from load outregs, track whether an ALU operand was traversed
        starts = [o for i in ins if kind[i] == "TLoad" for s, o in ops_of.get(i, []) if s == "outreg"]
        seen = set()
        stack = [(o, False) for o in starts]
        while stack:
            o, via = stack.pop()
            if (o, via) in seen:
                continue
            seen.add((o, via))
            if o in targets and via:
                alu_on_path = True
                break
            for nb in edges.get(o, ()):
                stack.append((nb, via or kind.get(owner.get(nb), "") in ("TOthern", "TOtherx")))
    return {"n": len(ins), "operands": len(owner), "states": len(states), "reg_s": len(regs),
            "unresolved_br": sum(1 for b in brs if b not in res),
            "spacer_br": sum(1 for b in brs if not ops_of.get(b)), "alu_on_xm_path": alu_on_path,
            "kinds": sorted(kind[i][1:] for i in ins)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    a = ap.parse_args()
    out = {}
    for d in sorted((Path(a.ws) / "bench/dump").iterdir()):
        files = sorted(d.glob("inst-*.txt"))
        if not files:
            continue
        rows = [one(f) for f in files]
        k = len(rows)
        out[d.name] = {
            "dumped": k,
            "alu_on_xm_path_frac": round(sum(r["alu_on_xm_path"] for r in rows) / k, 3),
            "operands_max": max(r["operands"] for r in rows),
            "operands_mean": round(sum(r["operands"] for r in rows) / k, 1),
            "states_max": max(r["states"] for r in rows),
            "reg_s_max": max(r["reg_s"] for r in rows),
            "unresolved_br_max": max(r["unresolved_br"] for r in rows),
            "spacer_br_mean": round(sum(r["spacer_br"] for r in rows) / k, 2),
            "has_alu_frac": round(sum(any(x in ("Othern", "Otherx") for x in r["kinds"]) for r in rows) / k, 3),
        }
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
