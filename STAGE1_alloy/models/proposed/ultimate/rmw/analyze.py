#!/usr/bin/env python3
"""Analyze scratch Alloy instances of STT_6_rmw_u (role census + core relabel check)."""
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path

S = Path(__file__).parent
SLOTS = ["inreg", "inaddr", "inmem", "outreg", "outmem"]
KIND = {"TLoad": "ld", "TStore": "st", "TBranchn": "br_n", "TBranchx": "br_x",
        "TOthern": "oth_n", "TOtherx": "oth_x", "TRmw": "rmw"}


def parse(path):
    rels = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^this/([A-Za-z_]+(?:<:[A-Za-z_]+)?)=\{(.*)\}$", line)
        if not m:
            continue
        body = m.group(2).strip()
        tuples = []
        if body:
            for t in body.split(", "):
                tuples.append(tuple(t.split("->")))
        rels[m.group(1)] = tuples
    return rels


def model(rels):
    instrs = [a for (a,) in rels.get("Instruction", [])]
    spo = dict(rels.get("Instruction<:spo", []))
    first = [i for i in instrs if i not in spo.values()]
    order = []
    cur = first[0] if first else None
    while cur:
        order.append(cur)
        cur = spo.get(cur)
    kind = {i: KIND[k.split("$")[0]] for (i, k) in rels["Instruction<:kind"]}
    res = {i for (i, _) in rels.get("Instruction<:isresolved", [])}
    com = {i for (i, _) in rels.get("Instruction<:iscommitted", [])}
    xm = {i for (i, _) in rels.get("Instruction<:isxm", [])}
    ops = {s: {} for s in SLOTS}
    owner = {}
    for s in SLOTS:
        for (i, o) in rels.get(f"Instruction<:{s}", []):
            ops[s].setdefault(i, []).append(o)
            owner[o] = (i, s)
    st = dict(rels.get("Operand<:opstate", []))
    rf = rels.get("Operand<:rf", [])
    ddi = rels.get("Operand<:ddi", [])
    return dict(order=order, kind=kind, res=res, com=com, xm=xm, ops=ops,
                owner=owner, st=st, rf=rf, ddi=ddi)


def canon(m):
    """Lexicographically minimal string over state renamings and same-slot operand orders."""
    order = m["order"]
    idx = {i: n for n, i in enumerate(order)}
    states = sorted(set(m["st"].values()))
    best = None
    slot_lists = []
    for i in order:
        for s in SLOTS:
            slot_lists.append((i, s, m["ops"][s].get(i, [])))
    perms_per_slot = [list(itertools.permutations(l)) for (_, _, l) in slot_lists]
    for sperm in itertools.permutations(range(len(states))):
        sname = {states[k]: f"S{sperm[k]}" for k in range(len(states))}
        for choice in itertools.product(*perms_per_slot):
            oid = {}
            parts = []
            for (i, s, _), ch in zip(slot_lists, choice):
                for k, o in enumerate(ch):
                    oid[o] = f"{idx[i]}.{s}{k}"
            for i in order:
                parts.append(f"{idx[i]}:{m['kind'][i]}:{'R' if i in m['res'] else 'u'}"
                             f"{'C' if i in m['com'] else 'n'}{'X' if i in m['xm'] else '-'}")
            for (i, s, _), ch in zip(slot_lists, choice):
                for o in ch:
                    parts.append(f"{oid[o]}={sname[m['st'][o]]}")
            parts += sorted(f"rf {oid[a]}>{oid[b]}" for (a, b) in m["rf"])
            parts += sorted(f"ddi {oid[a]}>{oid[b]}" for (a, b) in m["ddi"])
            key = "|".join(parts)
            if best is None or key < best:
                best = key
    return best


def relabel_rmw_as_ld(m):
    """RMW -> ld: drop outmem, inreg and their ddi/rf edges (the ld analogue)."""
    m = json.loads(json.dumps({k: (sorted(v) if isinstance(v, set) else v) for k, v in m.items()}))
    m["res"], m["com"], m["xm"] = set(m["res"]), set(m["com"]), set(m["xm"])
    drop = set()
    for i, k in list(m["kind"].items()):
        if k == "rmw":
            m["kind"][i] = "ld"
            for s in ("outmem", "inreg"):
                drop |= set(m["ops"][s].pop(i, []))
    m["rf"] = [(a, b) for (a, b) in m["rf"] if a not in drop and b not in drop]
    m["ddi"] = [(a, b) for (a, b) in m["ddi"] if a not in drop and b not in drop]
    for o in drop:
        m["st"].pop(o, None)
    # a state used only by dropped operands disappears (no_extra_State)
    return m


def unresolved_before(m, i):
    k = m["order"].index(i)
    return any(m["kind"][j] in ("br_n", "br_x") and j not in m["res"] for j in m["order"][:k])


def roles(m):
    out = []
    for i in m["order"]:
        if m["kind"][i] != "rmw":
            continue
        ia = m["ops"]["inaddr"].get(i, [])
        ir = m["ops"]["inreg"].get(i, [])
        im = m["ops"]["inmem"][i][0]
        om = m["ops"]["outmem"][i][0]
        ia_src = [m["kind"][m["owner"][a][0]] for (a, b) in m["rf"] if b in ia]
        ir_src = [m["kind"][m["owner"][a][0]] for (a, b) in m["rf"] if b in ir]
        om_use = [m["kind"][m["owner"][b][0]] for (a, b) in m["rf"] if a == om]
        im_src = [m["kind"][m["owner"][a][0]] for (a, b) in m["rf"] if b == im]
        loc = m["st"][im]
        same_loc_lds = [j for j in m["order"] if m["kind"][j] == "ld" and j != i
                        and any(m["st"][o] == loc for o in m["ops"]["inmem"].get(j, []))]
        pos = ("xm" if i in m["xm"] else
               "committed" if i in m["com"] else
               "spec" if unresolved_before(m, i) else "uncommitted-nonspec")
        out.append(dict(pos=pos, inaddr=bool(ia), inaddr_src=",".join(ia_src) or "-",
                        inreg=bool(ir), inreg_src=",".join(ir_src) or "-",
                        inmem_src=",".join(im_src) or "-", outmem_use=",".join(om_use) or "-",
                        aliases_ld=bool(same_loc_lds)))
    return out


def census(d):
    files = sorted((S / "out" / d).glob("inst-*.txt"))
    c = Counter()
    nrmw = Counter()
    xmk = Counter()
    for f in files:
        m = model(parse(f))
        rs = roles(m)
        nrmw[len(rs)] += 1
        xmk[m["kind"][next(iter(m["xm"]))]] += 1
        for r in rs:
            c[(r["pos"], f"addr={r['inaddr']}:{r['inaddr_src']}", f"src={r['inreg']}:{r['inreg_src']}",
               f"in<-{r['inmem_src']}", f"out->{r['outmem_use']}", f"alias_ld={r['aliases_ld']}")] += 1
    return len(files), nrmw, xmk, c


def main():
    for d in sys.argv[1:]:
        n, nrmw, xmk, c = census(d)
        print(f"== {d}: {n} instances; #RMW per instance {dict(nrmw)}; xm kind {dict(xmk)}")
        for k, v in c.most_common(12):
            print(f"   {v:4d}  {' '.join(k)}")


if __name__ == "__main__":
    main()
