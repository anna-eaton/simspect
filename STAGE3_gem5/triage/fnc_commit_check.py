#!/usr/bin/env python3
"""Hits whose fnc never shows an O3PipeView retire: recover fnc's commit tick (2026-11-07).

On gem5-spt a committed store's O3PipeView record can be missing (the run ends
before it is dumped), so the checkers read fnc_retire = 0 and before_fnc passes
vacuously. This re-runs each such hit (spt_taint_probe.probe_one, --keep) and
takes fnc's commit tick from the Commit trace ("Committing instruction with
[sn:N] PC (0x<fnc>=>"), earliest committed instance, then re-tests
signal < fnc_commit.

    python3 fnc_commit_check.py --config <cfg> --testset <root> --facts facts.json --out out.json
"""
import argparse, json, re, sys, shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import spt_taint_probe as P

_COMMIT = re.compile(r"^\s*(\d+):.*Committing instruction with \[sn:(\d+)\] PC \(0x([0-9a-f]+)=>")


def one(args):
    stem, grid, mode, testset, config, signal = args
    r = P.probe_one((f"{stem}:{grid}", f"{testset}/{mode}", config, True))
    out = dict(stem=stem, mode=mode, grid=grid, reproduced=r.get("reproduced"), error=r.get("error"))
    try:
        ann = json.loads((Path(testset) / mode / "ann" / f"{stem}.ann.json").read_text())
        fnc = ann["commit_boundary"]["first_noncommitted"]
        wd = Path(r["workdir"])
        import gem5_common as gc
        binary = wd / stem
        fnc_pc = gc.resolve_pc(binary, stem, fnc) if binary.exists() else int(fnc["addr"])
        ticks = []
        with open(wd / "m5out" / "pipeview.txt") as f:
            for ln in f:
                m = _COMMIT.match(ln)
                if m and int(m.group(3), 16) == fnc_pc:
                    ticks.append(int(m.group(1)))
        sig = r.get("xmit_signal") or signal
        out.update(fnc_pc=hex(fnc_pc), fnc_commit=min(ticks) if ticks else None, signal=sig,
                   before_fnc_by_commit=(sig < min(ticks)) if ticks and sig else None)
        shutil.rmtree(wd, ignore_errors=True)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--testset", required=True)
    ap.add_argument("--facts", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    F = json.load(open(a.facts)); todo = {}
    for f in F:
        if not f["fnc_retire"]:
            k = (f["stem"], int(f["grid"][4:]), f["mode"])
            todo.setdefault(k, f["signal"])
    with ProcessPoolExecutor(a.jobs) as ex:
        res = list(ex.map(one, [(s, g, m, a.testset, a.config, sig) for (s, g, m), sig in sorted(todo.items())]))
    json.dump(res, open(a.out, "w"), indent=1)
    for r in res:
        print(r["mode"], r["stem"], r["grid"], r.get("reproduced"), r.get("fnc_commit"), r.get("signal"), r.get("before_fnc_by_commit"), r.get("error"))


if __name__ == "__main__":
    main()
