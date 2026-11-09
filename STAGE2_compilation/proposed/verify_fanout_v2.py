#!/usr/bin/env python3
"""
verify_fanout_v2.py: check a fanout-v2 testset (2026-11-08, fpr-fanout session).

For each <stem>.ann.json carrying "fanout_v2", re-derive the pass-4 program from
the XML (same reg_naming default as batch_generate), apply the recorded
splices (value-preserving op on the edge's register, rewiring the consumer and
later readers) and fillers (read 2 registers, write a register the program
never uses) as dataflow ops, and check:
  * every Alloy instruction's register/memory source still descends from its
    original Alloy writer (rf edges intact; ddi edges are intra-instruction and
    untouched by insertions);
  * every recorded splice lies on that edge's def chain;
  * no filler writes a register any Alloy instruction reads or writes;
  * for an ld transmitter fed by a load: the producer still feeds the address,
    and whether a splice puts an ALU on that path.
Read-only. Usage: verify_fanout_v2.py <xml_dir> <llvm_or_ann_dir> [--mode mispredict_not_taken]
"""
import argparse, json, random, sys, zlib, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure_xmit_path_alu as M   # to_ops, analyze, all_edges_intact, producer_of
P = M.P

def r4_for(xml, stem, mode, rn):
    r1 = P.pass1_specify_state_a(P.parse_alloy_xml(xml), write_out=False)
    vseed = zlib.crc32(f"{stem}_v0".encode())   # batch_generate.run_pipeline's seed
    random.seed(vseed)
    r2 = P.pass2_specify_instructions(r1, write_out=False)
    r25 = P.pass2_5_specify_branches(r2, branch_mode=mode, write_out=False)
    ril = P.pass_interleave(r25, None, random.Random(vseed ^ 0xABCD_1234))
    r3 = P.pass3_assign_operands(ril, write_out=False, reg_naming=rn)
    return P.pass4_ssa(r3, write_out=False)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("xml_dir"); ap.add_argument("ann_dir")
    ap.add_argument("--mode", default="mispredict_not_taken"); a = ap.parse_args()
    tot = collections.Counter(); bad = []
    for annf in sorted(Path(a.ann_dir).glob("*.ann.json")):
        stem = annf.name[:-9]; ann = json.loads(annf.read_text())
        fv = ann.get("fanout_v2")
        if fv is None: continue
        rnr = ann.get("reg_naming")
        rn = {"mode": "random", "seed": rnr["seed"]} if rnr else {"mode": "sorted"}
        r4 = r4_for((Path(a.xml_dir) / f"{stem}.xml").read_text(), stem, a.mode, rn)
        base = M.to_ops(r4["instructions"])
        # locked/Alloy registers
        alloy_regs = {x for o in base for x in (o["srcs"] | o["dsts"]) if x.startswith("r:")}
        idx = {o["pc"]: i for i, o in enumerate(base) if not o["synthetic"]}
        new = [dict(o) for o in base]
        ins = []   # (position index in base, op)
        for f in fv["fillers"]:
            d = "r:" + f["dst"]
            if d in alloy_regs: bad.append((stem, "filler writes Alloy reg", f)); tot["filler_bad"] += 1
            ins.append((idx[f["before_pc"]], dict(kind="other_n", alu=True, srcs={"r:" + s for s in f["srcs"]}, dsts={d}, xm=False, pc=-1, synthetic=True, atom="F")))
        for s in fv["splices"]:
            if s.get("shared_with_previous"): continue
            r = "r:" + s["reg"]
            ins.append((idx[s["consumer_pc"]], dict(kind="other_n", alu=True, srcs={r}, dsts={r}, xm=False, pc=-1, synthetic=True, atom="S%d" % s["consumer_pc"])))
        otb = fv.get("otb") or {}
        if otb.get("applied"):
            l2 = "r:" + otb["l2_reg"]; R = "r:" + otb["merge_reg"]
            if l2 in alloy_regs: bad.append((stem, "OTB L2 writes Alloy reg"))
            ins.append((idx[otb["l2_before_pc"]], dict(kind="ld", alu=False, srcs=set(), dsts={l2}, xm=False, pc=-1, synthetic=True, atom="L2")))
            ins.append((idx[otb["xmit_pc"]], dict(kind="other_n", alu=True, srcs={R, l2}, dsts={R}, xm=False, pc=-1, synthetic=True, atom="OTB")))
        for pos, op in sorted(ins, key=lambda t: t[0], reverse=True):
            new.insert(pos, op)
        ok = M.all_edges_intact(base, new)
        tot["tests"] += 1; tot["edges_intact"] += ok
        if not ok: bad.append((stem, "edge broken"))
        tot["splices"] += len(fv["splices"]); tot["fillers"] += len(fv["fillers"])
        if otb.get("applied"):
            tot["otb_applied"] += 1
            # shape: the transmitter's address descends from BOTH the Alloy producer and L2,
            # through the merge ALU, and L2 sits after br_r and before br_u (older than the producer)
            xi = next(i for i, o in enumerate(new) if o["xm"])
            m = xi - 1
            while new[m]["atom"] != "OTB": m -= 1
            li = next(i for i, o in enumerate(new) if o["atom"] == "L2")
            pi = next(i for i, o in enumerate(new) if o["pc"] == otb["producer_pc"] and not o["synthetic"])
            ok_shape = (otb["br_r_pc"] < otb["l2_before_pc"] <= otb["br_u_pc"] < otb["producer_pc"] < otb["xmit_pc"]
                        and li < pi and M.analyze(new, base[[i for i, o in enumerate(base) if o["pc"] == otb["producer_pc"]][0]]["atom"])[0])
            # L2 reaches the merge: last writer of l2 before the merge is L2
            w = max(i for i in range(m) if ("r:" + otb["l2_reg"]) in new[i]["dsts"])
            ok_shape = ok_shape and new[w]["atom"] == "L2"
            tot["otb_shape_ok"] += ok_shape
            if not ok_shape: bad.append((stem, "OTB shape"))
        elif otb:
            tot["otb_skip:" + otb.get("why", "")] += 1
        prod, _ = M.producer_of(r4)
        if prod:
            rp, ra = M.analyze(new, prod)
            tot["ld_xmit_load_fed"] += 1; tot["xmit_path_intact"] += rp; tot["alu_on_xmit_path"] += ra
            if any(s["xmit_edge"] for s in fv["splices"]) and not ra: bad.append((stem, "xmit splice not on path"))
    print(dict(tot)); print("problems:", bad[:10], len(bad))
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
