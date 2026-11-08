#!/usr/bin/env python3
"""Recon STLF taint-bypass evidence for every ld hit of a recon-modded campaign (2026-11-08).

For each (mode, stem) with an ld hit, re-runs the test faithfully at its lowest
hit grid point (spt_taint_probe.probe_one, --keep) and reads the trace right
after each of the transmitter's "Executing load" lines (the first that
forwarded and became ready is kept; a squashed first execution can precede it):
  stl            the LSQ "STL_CHECK: load PC <xmit> isTainted=. isSpeculative=." line
  fwd            a "Forwarding from store idx N to load" line follows
  ready_tick     Commit "[sn:<xmit>] ready within ROB"
  ctrl_visible   earliest resolve_visible of a held (unresolved) branch
  ready_in_window  ready_tick < ctrl_visible
Writes {"<mode>/<stem>": {...}} for diag_recon_stlf_bypass.py. Deletes each kept
workdir afterwards (exact path from the probe record).

    python3 recon_stlf_check.py --config <cfg> --testset <root> --facts facts.json --out recon_stlf_evidence.json
"""
import argparse, json, re, shutil, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import spt_taint_probe as P


def one(args):
    stem, grid, mode, testset, config = args
    r = P.probe_one((f"{stem}:{grid}", f"{testset}/{mode}", config, True))
    out = dict(stem=stem, mode=mode, grid=grid, reproduced=r.get("reproduced"), error=r.get("error"),
               stl="", fwd=False, ready_tick=None, ctrl_visible=None, ready_in_window=False)
    wd = r.get("workdir")
    try:
        if wd and r.get("xmit_pc"):
            x = r["xmit_pc"][2:]
            L = open(Path(wd) / "m5out" / "pipeview.txt").read().splitlines()
            idx = [k for k, l in enumerate(L) if "Executing load PC (0x" + x in l]
            out["n_exec"] = len(idx)
            # Every dynamic execution of the xmit; keep the first that forwarded
            # and became ready (a squashed first execution can precede it).
            for k in idx:
                sn = re.search(r"sn:(\d+)", L[k]).group(1)
                win = L[k:k + 6]
                stl = next((l.split(": ", 2)[-1] for l in win if "STL_CHECK" in l), "")
                fwd = any("Forwarding from store" in l for l in win)
                rdy = next((int(l.split(":")[0]) for l in L[k:] if f"[sn:{sn}] ready within ROB" in l), None)
                if not out["stl"] or (fwd and rdy):
                    out.update(stl=stl, fwd=fwd, ready_tick=rdy, xmit_seq=int(sn))
                if fwd and rdy:
                    break
            ctrl = [d for s in (r.get("br_events") or {}).values() for d in s.values() if d.get("resolve_hold")]
            out["ctrl_visible"] = min(d["resolve_visible"] for d in ctrl if d.get("resolve_visible")) if ctrl else None
            out["ready_in_window"] = bool(out["ready_tick"] and out["ctrl_visible"] and out["ready_tick"] < out["ctrl_visible"])
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        if wd:
            shutil.rmtree(Path(wd).parent if Path(wd).name == "m5out" else wd, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--testset", required=True)
    ap.add_argument("--facts", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=10)
    ap.add_argument("--only", nargs="*", help="restrict to <mode>/<stem> keys")
    a = ap.parse_args()
    todo = {}
    for f in json.load(open(a.facts)):
        if a.only and f"{f['mode']}/{f['stem']}" not in a.only:
            continue
        if f["kind"] == "ld":
            k = (f["mode"], f["stem"]); g = int(f["grid"][4:])
            todo[k] = min(todo.get(k, g), g)
    with ProcessPoolExecutor(a.jobs) as ex:
        res = list(ex.map(one, [(s, g, m, a.testset, a.config) for (m, s), g in sorted(todo.items())]))
    json.dump({f"{r['mode']}/{r['stem']}": r for r in res}, open(a.out, "w"), indent=1)
    sig = sum(1 for r in res if r["reproduced"] and "isTainted=1 isSpeculative=1" in r["stl"] and r["fwd"] and r["ready_in_window"])
    print(f"{len(res)} tests, {sig} with the full STLF-bypass signature")


if __name__ == "__main__":
    main()
