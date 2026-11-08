#!/usr/bin/env python3
"""Census of SPT-model over-generation shapes over a whole testset's XML (2026-11-08).

Per instance (pure XML, no gem5), with the transmitter operand X = the xmit's
inaddr (ld, str) or inreg (br_x):
  stale_rf        some rf edge reads a state past a newer writer of that state
                  (what STT_6.als:163 rf_from_most_recent_writer forbids;
                  SPT_6_oneLP.als lacks the fact). Concretization then feeds the
                  consumer the newer value, so the program differs from the instance.
  stale_rf_on_x   ... and that edge feeds X itself
  x_no_load_cone  X's producer cone (rf edges, spo-before) reaches no load:
                  X is constant-derived, which SPT never taints
  unfed_read      some register input has a state with an earlier writer but no
                  rf edge (concretization gives it that writer's value anyway)
    python3 spt_testset_shapes.py <testset>/xml --out census.json
"""
import argparse, collections, json, re
import xml.etree.ElementTree as ET
from pathlib import Path


def parse(p):
    r = ET.parse(p).getroot().find("instance")
    return {fl.get("label"): [tuple(a.get("label") for a in t.findall("atom")) for t in fl.findall("tuple")]
            for fl in r.findall("field")}


def shapes(F):
    kind = dict(F["kind"]); op = dict(F.get("opstate", []))
    pos = {a: int(re.search(r"IX(\d+)", b).group(1)) for a, b in F["idx"]}
    owner, rel_of = {}, {}
    for rel in ("inreg", "inaddr", "inmem", "outreg", "outmem"):
        for a, b in F.get(rel, []):
            owner[b] = a; rel_of[b] = rel
    rf = F.get("rf", []); src = {c: p for p, c in rf}
    outs = [b for rel in ("outreg", "outmem") for a, b in F.get(rel, [])]
    xm = [a for a, *_ in F["isxm"]][0]; xk = kind[xm].split("$")[0]
    X = [b for a, b in F.get("inreg" if xk == "TBranchx" else "inaddr", []) if a == xm]
    out = dict(kind={"TLoad": "ld", "TStore": "str", "TBranchx": "br_x"}.get(xk, xk))
    stale = []
    for p, c in rf:
        s = op.get(p)
        for w in outs:
            if w != p and op.get(w) == s and pos[owner[p]] < pos[owner[w]] < pos[owner[c]]:
                stale.append(c)
    out["stale_rf"] = bool(stale); out["stale_rf_on_x"] = any(c in X for c in stale)
    # producer cone of X over rf edges
    seen, st, load = set(), list(X), False
    while st:
        o = st.pop()
        if o in seen:
            continue
        seen.add(o)
        p = src.get(o)
        if p is None:
            continue
        i = owner[p]
        if kind[i].startswith("TLoad"):
            load = True; continue
        st.extend(b for rel in ("inreg", "inaddr", "inmem") for a, b in F.get(rel, []) if a == i)
    out["x_no_load_cone"] = bool(X) and not load
    unfed = False
    for rel in ("inreg", "inaddr"):
        for a, b in F.get(rel, []):
            if b in src or op.get(b) is None:
                continue
            if any(op.get(w) == op[b] and pos[owner[w]] < pos[a] for w in outs):
                unfed = True
    out["unfed_read"] = unfed
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("xml_dir", type=Path); ap.add_argument("--out", type=Path)
    ap.add_argument("--stems", type=Path, help="optional JSON list of stems to restrict to")
    a = ap.parse_args()
    stems = json.load(open(a.stems)) if a.stems else None
    files = [a.xml_dir / f"{s}.xml" for s in stems] if stems else sorted(a.xml_dir.glob("inst-*.xml"))
    c = collections.Counter(); per = {}
    for f in files:
        try:
            s = shapes(parse(f))
        except Exception as e:
            c["parse_error"] += 1; continue
        per[f.stem] = s
        c[("n", s["kind"])] += 1
        for k in ("stale_rf", "stale_rf_on_x", "x_no_load_cone", "unfed_read"):
            if s[k]:
                c[(k, s["kind"])] += 1
        if not (s["stale_rf"] or s["x_no_load_cone"] or s["unfed_read"]):
            c[("clean", s["kind"])] += 1
    for k, n in sorted(c.items(), key=str):
        print(n, k)
    if a.out:
        a.out.write_text(json.dumps(dict(counts={str(k): v for k, v in c.items()}, per=per)))


if __name__ == "__main__":
    main()
