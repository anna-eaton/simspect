#!/usr/bin/env python3
"""
measure_xmit_path_alu.py — fanout v2 measurement (2026-11-08, fpr-fanout session).

For each XML (ld transmitter whose address is rf-fed by a load), concretize with
parsexml passes 1-4 and measure, per interleave approach, how often an ALU op
ends up on the def chain from the Alloy producer load to the transmitter's
address register, and whether that producer is still an ancestor (path intact).
Read-only: never writes into testsets/ or results/; parsexml is imported as is.

Approaches:
  none       no interleave (today's default testsets)
  current    today's pass_interleave with the given interleave config (N variants)
  rand_any   prototype: K random ALU fillers inserted anywhere before the xmit,
             sources AND destination drawn from every register the test uses
             (locked included), then a post-check keeps only path-intact variants
  rand_ro    prototype: same fillers, but the destination is never a locked
             (Alloy-specified) register: fillers may read path registers, never write them
  splice     prototype: one ALU op spliced onto the producer->xmit rf edge
             (reads the producer's outreg, writes the xmit's address register)

Usage: python3 measure_xmit_path_alu.py <xml_dir> [--n 300] [--variants 4]
         [--interleave-config runconfigs/fixed_20261030/STT_6_interleave_reconmodded_fixed.jsonc]
"""
import argparse, json, random, re, sys, zlib, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "STAGE2_compilation"))
import parsexml as P
P.reload_tables(str(ROOT / "STAGE2_compilation/instruction_tables/instructions.jsonc"))

def slot(rec, n):
    for l in rec["slots"].values():
        for s in l:
            if s["slot"] == n: return s

def to_ops(ins):
    """Linear dataflow ops: dict(kind, alu, srcs(set of 'r:reg'/'m:off'), dsts, xm, pc)."""
    ops = []
    for r in ins:
        c = r.get("concrete_instruction") or ""
        srcs, dsts = set(), set()
        g = lambda n: slot(r, n) or {}
        if c == "load":
            if g("inaddr").get("specified") and g("inaddr").get("assigned"): srcs.add("r:" + g("inaddr")["assigned"])
            elif g("inmem").get("assigned_offset") is not None: srcs.add("m:%d" % g("inmem")["assigned_offset"])
            if g("outreg").get("assigned") and g("outreg").get("ssa_name"): dsts.add("r:" + g("outreg")["assigned"])
        elif c == "store":
            for n in ("inreg0", "inaddr"):
                if g(n).get("assigned") and g(n).get("ssa_name"): srcs.add("r:" + g(n)["assigned"])
            if g("outmem").get("assigned_offset") is not None: dsts.add("m:%d" % g("outmem")["assigned_offset"])
        else:
            for n in ("inreg0", "inreg1"):
                if g(n).get("assigned") and g(n).get("ssa_name"): srcs.add("r:" + g(n)["assigned"])
            if g("outreg").get("assigned") and g("outreg").get("ssa_name"): dsts.add("r:" + g("outreg")["assigned"])
        alu = not (c == "load" or c == "store" or c.startswith("br"))
        ops.append(dict(kind=r["kind"], alu=alu, srcs=srcs, dsts=dsts, xm=bool(r.get("xm")), pc=r["pc"],
                        synthetic=bool(r.get("synthetic")), atom=r["instruction"]))
    return ops

def analyze(ops, producer_atom):
    """(path_intact, alu_on_path) for the xmit's address operand."""
    xi = next(i for i, o in enumerate(ops) if o["xm"])
    # backward ancestor walk with last-writer semantics
    def writer(loc, before):
        for j in range(before - 1, -1, -1):
            if loc in ops[j]["dsts"]: return j
        return None
    # node j reaches producer? and via ALU?
    memo = {}
    def reach(j):  # returns (reaches_producer, reaches_producer_through_alu)
        if j in memo: return memo[j]
        memo[j] = (False, False)
        o = ops[j]
        if o["atom"] == producer_atom and not o["synthetic"]:
            memo[j] = (True, False); return memo[j]
        rp = ra = False
        for s in o["srcs"]:
            w = writer(s, j)
            if w is None: continue
            a, b = reach(w)
            rp |= a; ra |= b or (a and o["alu"])
        memo[j] = (rp, ra); return memo[j]
    srcs = ops[xi]["srcs"]
    rp = ra = False
    for s in srcs:
        w = writer(s, xi)
        if w is None: continue
        a, b = reach(w)
        rp |= a; ra |= b
    return rp, ra

def all_edges_intact(base, new):
    """Every Alloy op's source still descends from its original writer (no clobber)."""
    def writer(ops, loc, before):
        for j in range(before - 1, -1, -1):
            if loc in ops[j]["dsts"]: return j
        return None
    def anc(ops, j, target_atom, seen=None):
        seen = seen or set()
        if j in seen: return False
        seen.add(j)
        if ops[j]["atom"] == target_atom and not ops[j]["synthetic"]: return True
        if not ops[j]["synthetic"]: return False      # stop at another Alloy op
        return any(anc(ops, w, target_atom, seen) for s in ops[j]["srcs"] for w in [writer(ops, s, j)] if w is not None)
    idx = {o["atom"]: i for i, o in enumerate(new) if not o["synthetic"]}
    for j, o in enumerate(base):
        if o["synthetic"]: continue
        for s in o["srcs"]:
            w0 = writer(base, s, j)
            if w0 is None: continue
            nj = idx[o["atom"]]; w1 = writer(new, s, nj)
            if w1 is None or not anc(new, w1, base[w0]["atom"]): return False
    return True

def base_r4(xml, stem, icfg=None, v=0):
    r1 = P.pass1_specify_state_a(P.parse_alloy_xml(xml), write_out=False)
    vseed = zlib.crc32((f"{stem}_v{v}" if icfg else stem).encode())
    random.seed(vseed)
    r2 = P.pass2_specify_instructions(r1, write_out=False)
    r25 = P.pass2_5_specify_branches(r2, branch_mode="mispredict_not_taken", write_out=False)
    ril = P.pass_interleave(r25, icfg, random.Random(vseed ^ 0xABCD_1234))
    return P.pass4_ssa(P.pass3_assign_operands(ril, write_out=False), write_out=False)

def producer_of(r4):
    ins = r4["instructions"]
    xm = next((r for r in ins if r.get("xm")), None)
    if not xm or xm.get("concrete_instruction") != "load": return None, None
    ia = slot(xm, "inaddr")
    if not (ia and ia.get("specified") and ia.get("ssa_name")): return None, None
    for r in ins:
        if r is not xm and r.get("concrete_instruction") == "load" and (slot(r, "outreg") or {}).get("ssa_name") == ia["ssa_name"]:
            return r["instruction"], ia["assigned"]
    return None, None

def fillers(ops, locked, rng, mode, k):
    regs = sorted({x for o in ops for x in (o["srcs"] | o["dsts"]) if x.startswith("r:")})
    xi = next(i for i, o in enumerate(ops) if o["xm"])
    new = list(ops)
    for _ in range(k):
        pos = rng.randint(0, xi); xi += 1
        srcs = set(rng.sample(regs, min(len(regs), rng.choice([1, 2]))))
        pool = regs if mode == "rand_any" else [r for r in regs if r[2:] not in locked] or regs
        new.insert(pos, dict(kind="other_n", alu=True, srcs=srcs, dsts={rng.choice(pool)}, xm=False, pc=-1, synthetic=True, atom="F"))
    return new

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xml_dir"); ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--variants", type=int, default=4)
    ap.add_argument("--interleave-config", default=str(ROOT / "runconfigs/fixed_20261030/STT_6_interleave_reconmodded_fixed.jsonc"))
    a = ap.parse_args()
    t = re.sub(r"^\s*//.*$", "", Path(a.interleave_config).read_text(), flags=re.M)
    icfg = json.loads(t)["interleave"]
    xs = sorted(Path(a.xml_dir).glob("inst-*.xml"))[: a.n]
    tot = collections.Counter(); n_elig = 0
    for f in xs:
        stem = f.stem; xml = f.read_text()
        r4 = base_r4(xml, stem)
        prod, addr = producer_of(r4)
        if not prod: continue
        n_elig += 1
        ops = to_ops(r4["instructions"]); locked = set(r4["locked_registers"].values())
        rp, ra = analyze(ops, prod); tot["none", "intact"] += rp; tot["none", "alu"] += ra; tot["none", "n"] += 1
        for v in range(icfg.get("variants_per_instance", 1)):
            r4v = base_r4(xml, stem, icfg, v)
            rp, ra = analyze(to_ops(r4v["instructions"]), prod)
            tot["current", "intact"] += rp; tot["current", "alu"] += ra; tot["current", "n"] += 1
        for mode in ("rand_any", "rand_ro"):
            for v in range(a.variants):
                rng = random.Random(zlib.crc32(f"{mode}:{stem}:{v}".encode()))
                nops = fillers(ops, locked, rng, mode, rng.randint(1, 4))
                rp, ra = analyze(nops, prod)
                ok = all_edges_intact(ops, nops)
                tot[mode, "n"] += 1; tot[mode, "intact"] += rp; tot[mode, "alu"] += ra and rp
                tot[mode, "alledges"] += ok; tot[mode, "alu_alledges"] += ra and rp and ok
        # splice: ALU reads the producer's outreg, writes the xmit address reg, inserted just before the xmit
        xi = next(i for i, o in enumerate(ops) if o["xm"])
        pi = next(i for i, o in enumerate(ops) if o["atom"] == prod)
        sp = list(ops); sp.insert(xi, dict(kind="other_n", alu=True, srcs=set(ops[pi]["dsts"]), dsts={"r:" + addr}, xm=False, pc=-1, synthetic=True, atom="S"))
        rp, ra = analyze(sp, prod); tot["splice", "n"] += 1; tot["splice", "intact"] += rp; tot["splice", "alu"] += ra
        ok = all_edges_intact(ops, sp); tot["splice", "alledges"] += ok; tot["splice", "alu_alledges"] += ra and ok
    print(f"XMLs read {len(xs)}, ld xmit with load-fed address {n_elig}")
    for m in ("none", "current", "rand_any", "rand_ro", "splice"):
        n = tot[m, "n"]
        print(f"{m:9s} variants={n:5d}  path_intact={tot[m,'intact']:5d} ({100*tot[m,'intact']/max(n,1):5.1f}%)  ALU_on_intact_path={tot[m,'alu']:5d} ({100*tot[m,'alu']/max(n,1):5.1f}%)"
              + (f"  all_alloy_edges_intact={tot[m,'alledges']} ({100*tot[m,'alledges']/max(n,1):.1f}%)  ALU_on_path_and_all_edges_intact={tot[m,'alu_alledges']} ({100*tot[m,'alu_alledges']/max(n,1):.1f}%)" if m in ("rand_any","rand_ro","splice") else ""))

if __name__ == "__main__":
    main()
