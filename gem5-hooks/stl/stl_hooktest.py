#!/usr/bin/env python3
"""Smoke test for the SimSpect-STL gem5 hooks (gem5-hooks/stl/).

For each test in <testdir>/{asm,ann}: build, run gem5 with the STL flags, and
report, from the trace alone:
  hold     an stl_hold for the annotated store S
  pred     pred_no_alias / pred_alias for the annotated load L
  l_exec   L's first dynamic instance executed (LSQ "Executing load") before stl_release
  squash   a mem_order_squash with seq=L(first) cause=S
  xmit     for an ld transmitter: first dynamic instance's cache fate + packet tick,
           and whether that tick is in [stl_hold, stl_release)
Env (set before import): SIMSPECT_GEM5_BIN, SIMSPECT_SE_CONFIG, SIMSPECT_STL_*.
"""
import json, os, sys, tempfile, shutil, re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "/tests/simspect/STAGE3_gem5")
import gem5_common as gc

def one(s_path: Path, ann_path: Path, scheme: int) -> dict:
    name = s_path.stem
    wd = Path(tempfile.mkdtemp(prefix=f"stlhook_{name}_"))
    r = dict(name=name)
    try:
        ann = json.loads(ann_path.read_text())
        r["kind"] = ann["xmit"]["kind"]
        pairs = ann["stl_annotations"]
        s_pc = int(pairs[0]["store_addr"])
        l_pcs = [int(p["load_addr"]) for p in pairs if int(p["store_addr"]) == s_pc]
        r["n_loads"] = len(l_pcs)
        binary = gc.build_binary(s_path, wd)
        x_pc = gc.resolve_pc(binary, name, ann["xmit"])
        gc._scheme = scheme
        trace = gc.run_gem5(binary, wd, ann_path=ann_path, fnc_pc=None)
        ev = [e for e in gc.parse_simspect_events(trace) if e["struct"] == "STL"]
        lsq = gc.parse_lsq(trace)
        holds = [e for e in ev if e["kind"] == "stl_hold" and e["pc"] == s_pc]
        rels = [e for e in ev if e["kind"] == "stl_release" and e["pc"] == s_pc]
        preds = [e for e in ev if e["kind"] in ("pred_no_alias", "pred_alias") and e["pc"] in l_pcs]
        # first dynamic instance of each annotated load
        l_firsts = [min(lsq[pc], key=lambda x: x["sn"]) for pc in l_pcs if lsq.get(pc)]
        l_first = min(l_firsts, key=lambda x: x["sn"]) if l_firsts else None
        s_seq = holds[0]["seq"] if holds else None
        sq = [e for e in ev if e["kind"] == "mem_order_squash"]
        r.update(
            hold=bool(holds), release=bool(rels),
            t_hold=holds[0]["tick"] if holds else None,
            t_rel=rels[0]["tick"] if rels else None,
            pred=preds[0]["kind"] if preds else None,
            l_exec=(l_first or {}).get("execute_tick"),
            n_squash=len(sq),
            squash_ok=any(e["seq"] in {x["sn"] for x in l_firsts} and e["cause"] == s_seq for e in sq),
            squashes=[(e["seq"], e["pc"], e["cause"]) for e in sq],
        )
        r["l_before_rel"] = bool(r["t_rel"] and any(
            x.get("execute_tick") and x["execute_tick"] < r["t_rel"] for x in l_firsts))
        r["valid"] = bool(r["hold"] and r["pred"] == "pred_no_alias" and r["l_before_rel"] and r["squash_ok"])
        if r["kind"] == "ld":
            x_recs = sorted(lsq.get(x_pc, []), key=lambda x: x["sn"])
            if x_recs:
                x0 = x_recs[0]
                f = gc_fate([x0])
                r["x_fate"] = f["cache_fate"]          # shared check_ld gate (packet line)
                # recon builds print no "successfully sent out packet" line;
                # "Doing memory access" (lsq_unit.cc:2077) = not forwarded, goes to memory
                # The real send is "Memory request (pkt: ..) from inst [sn:N] was sent"
                # (lsq_unit.cc:1546); STT's delay unit bounces a tainted load AFTER
                # "Doing memory access" (lsq_unit.cc:2104), so that line is not a send.
                t = sent_tick(trace, x0["sn"])
                r["x_sn"], r["x_exec"], r["x_tick"] = x0["sn"], x0.get("execute_tick", 0), t
                r["x_mem"] = "sent" if t else ("executed_not_sent" if x0.get("execute_tick") else "never_executed")
                r["x_in_window"] = bool(t and r["t_hold"] and r["t_rel"] and r["t_hold"] <= t < r["t_rel"])
            else:
                r["x_fate"] = "no_lsq_record"
        r["status"] = "ok"
    except Exception as e:  # report, never hide
        r["status"] = "error"; r["error"] = f"{type(e).__name__}: {e}"[:400]
    finally:
        if os.environ.get("KEEP"):
            r["workdir"] = str(wd)
        else:
            shutil.rmtree(wd, ignore_errors=True)
    return r

_SENT = re.compile(r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*Memory request \(pkt: .*\) from inst \[sn:(\d+)\] was sent ")
def sent_tick(trace, sn):
    with open(trace, errors="replace") as f:
        for line in f:
            m = _SENT.match(line)
            if m and int(m.group(2)) == sn:
                return int(m.group(1))
    return 0

def gc_fate(recs):
    sys.path.insert(0, "/tests/simspect/STAGE3_gem5")
    from check_ld import _xmit_cache_fate
    return _xmit_cache_fate({0: recs}, 0)

if __name__ == "__main__":
    # absolute: gem5 runs in the per-test workdir, so a relative --stl-ann-file is not found
    testdir, scheme, out = Path(sys.argv[1]).resolve(), int(sys.argv[2]), Path(sys.argv[3])
    lim = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
    pairs = []
    for s in sorted((testdir / "asm").glob("*.s"))[:lim]:
        a = testdir / "ann" / (s.stem + ".ann.json")
        if a.exists():
            pairs.append((s, a))
    with ThreadPoolExecutor(32) as ex:
        res = list(ex.map(lambda p: one(p[0], p[1], scheme), pairs))
    out.write_text(json.dumps(res, indent=1))
    ok = [r for r in res if r["status"] == "ok"]
    print(f"{len(res)} tests, {len(ok)} ran, {len(res)-len(ok)} errors")
    for k in ("hold", "release", "l_before_rel", "squash_ok", "valid"):
        print(f"  {k:13s} {sum(1 for r in ok if r.get(k))}")
    print("  pred         ", {p: sum(1 for r in ok if r.get('pred') == p) for p in ("pred_no_alias", "pred_alias", None)})
    lds = [r for r in ok if r["kind"] == "ld"]
    print(f"  ld xmits {len(lds)}: gate fates", {f: sum(1 for r in lds if r.get('x_fate') == f) for f in sorted({r.get('x_fate') for r in lds}, key=str)})
    print(f"  ld xmits {len(lds)}: real send", {f: sum(1 for r in lds if r.get('x_mem') == f) for f in sorted({r.get('x_mem') for r in lds}, key=str)})
    print(f"  ld xmit packet in [hold,release): {sum(1 for r in lds if r.get('x_in_window'))}  (of valid: {sum(1 for r in lds if r.get('x_in_window') and r['valid'])})")
    for r in res:
        if r["status"] != "ok":
            print("  ERR", r["name"], r["error"])
