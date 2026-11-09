#!/usr/bin/env python3
"""
uv3_rmw_evidence.py: build the evidence file read by diag/diag_uv3_rmw.py for one
CleanupSpec footprint campaign on the RMW corpus (testsets_latest/STT_6_rmw).

Input: a testrun.py campaign dir run with pipeline.keep_tmp=true, so every raw
checker record in <campaign>/<mode>/_sweep_raw/*.json carries `workdir` (the kept
gem5 dir with m5out/pipeview.txt) and check_footprint's `offending` list.

For every hit record (issued_in_window True) it reads the trace and checks, per
offending (struct, line, event_ids):
  * every offending event is a `fill` on L1D (`req=st`, `msg=ST`) or on L2
    (`req=st`, `msg=GETX`) whose `pc` is the record's xmit_pc (the RMW's ldst
    issues as a write request: wiki/design/VOCAB_TABLES.md "RMW agent findings");
  * that instruction instance (`seq`) never retired (it is the squashed actor);
  * the trace has `L1D:cleanup_skip line=<line> seq=<seq> why=nohitinfo` for it.
Each variant entry also carries the record's cache_setup (the strategy the test
actually ran with: warm/cold; for gem5.cache_setup random it differs per test,
2026-11-09), so diag_uv3_rmw.py can report and split by it.
It writes <campaign>/diagnostics/uv3_rmw_evidence.json keyed "<mode>/<stem>"
(one entry per stem; a stem counts as UV3 only if every hitting variant matches),
gzips each hit's trace to <campaign>/diagnostics/traces/<mode>/<record>.pipeview.txt.gz
(a rerun after the workdirs are gone reads those gzipped copies instead),
and then deletes every kept workdir listed in the raw records (all made by this
campaign). Log: <campaign>/diagnostics/uv3_rmw_evidence.log.

Usage: python3 uv3_rmw_evidence.py <campaign_dir> [--keep-workdirs]
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path

PREFIX = "O3PipeView:simspect:"


def _open(trace: Path):
    """Plain trace, or the gzipped copy this script left in diagnostics/traces/ (2026-11-09)."""
    if trace.suffix == ".gz":
        return gzip.open(trace, "rt", errors="replace")
    return trace.open(errors="replace")


def parse_events(trace: Path):
    ev, retired = {}, set()
    skips = []
    with _open(trace) as fh:
        for ln in fh:
            if ln.startswith(PREFIX):
                parts = ln.rstrip("\n").split(":")
                tick, struct, kind = parts[2], parts[3], parts[4]
                kv = dict(p.split("=", 1) for p in parts[5:] if "=" in p)
                kv.update(tick=int(tick), struct=struct, kind=kind)
                if kv.get("id", "-") != "-":
                    ev[int(kv["id"])] = kv
                if struct == "L1D" and kind == "cleanup_skip":
                    skips.append(kv)
    return ev, skips


def retired_seqs(trace: Path) -> dict:
    """seq -> retire tick from the O3PipeView records (fetch line carries the seq)."""
    out, cur = {}, None
    with _open(trace) as fh:
        for ln in fh:
            if ln.startswith("O3PipeView:fetch:"):
                p = ln.split(":")
                cur = int(p[5]) if len(p) > 5 and p[5].strip().isdigit() else None
            elif ln.startswith("O3PipeView:retire:") and cur is not None:
                t = int(ln.split(":")[2])
                if t > 0:                      # retire tick 0 = squashed, never retired
                    out[cur] = t
                cur = None
    return out


def judge(rec: dict, trace: Path) -> dict:
    xpc = int(rec["xmit_pc"], 16)
    ev, skips = parse_events(trace)
    ret = retired_seqs(trace)
    off = rec.get("offending") or []
    if not off:
        return dict(uv3=False, why="no offending lines in record")
    if set(rec.get("terms_fired") or []) != {"under_clean"}:
        return dict(uv3=False, why=f"terms_fired={rec.get('terms_fired')}")
    details = []
    for o in off:
        line = o["line"]
        for eid in o["event_ids"]:
            e = ev.get(int(eid))
            if e is None:
                return dict(uv3=False, why=f"event id {eid} not in trace")
            want_msg = {"L1D": "ST", "L2": "GETX"}.get(e["struct"])
            if not (e["kind"] == "fill" and want_msg and e.get("req") == "st"
                    and e.get("msg") == want_msg and e.get("line") == line):
                return dict(uv3=False, why=f"event {eid} is {e['struct']}:{e['kind']} req={e.get('req')} "
                                           f"msg={e.get('msg')}, not an RMW write-request fill")
            if e.get("pc") in (None, "-") or int(e["pc"], 16) != xpc:
                return dict(uv3=False, why=f"event {eid} pc={e.get('pc')} is not the xmit {hex(xpc)}")
            seq = e.get("seq")
            if seq in (None, "-"):
                return dict(uv3=False, why=f"event {eid} has no seq")
            if int(seq) in ret:
                return dict(uv3=False, why=f"actor seq {seq} retired at {ret[int(seq)]}")
            sk = [s for s in skips if s.get("line") == line and s.get("seq") == seq
                  and s.get("why") == "nohitinfo"]
            if not sk:
                return dict(uv3=False, why=f"no L1D:cleanup_skip why=nohitinfo for line {line} seq {seq}")
            details.append(dict(struct=e["struct"], line=line, fill_id=int(eid), fill_tick=e["tick"],
                                seq=int(seq), skip_id=int(sk[0]["id"]), skip_tick=sk[0]["tick"]))
    return dict(uv3=True, why="every offending line was installed by the xmit RMW's write request "
                              "and its cleanup was skipped with why=nohitinfo", details=details)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign", type=Path)
    ap.add_argument("--keep-workdirs", action="store_true")
    a = ap.parse_args()
    camp = a.campaign.resolve()
    dg = camp / "diagnostics"; dg.mkdir(exist_ok=True)
    log = (dg / "uv3_rmw_evidence.log").open("a")

    def L(m):
        s = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {m}"; print(s, flush=True); log.write(s + "\n"); log.flush()

    L(f"START campaign={camp}")
    per_stem = defaultdict(list)
    workdirs = set()
    for mode_dir in sorted(camp.glob("mispredict_*")):
        mode = mode_dir.name
        for rf in sorted((mode_dir / "_sweep_raw").glob("*.json")):
            for rec in json.loads(rf.read_text()):
                wd = rec.get("workdir")
                if wd:
                    workdirs.add(wd)
                if rec.get("issued_in_window") is not True:
                    continue
                stem = rec["name"].split("__")[0]
                key = f"{mode}/{stem}"
                try:
                    tr = Path(wd) / "m5out" / "pipeview.txt" if wd else None
                    gz = dg / "traces" / mode / f"{rec['name']}.pipeview.txt.gz"
                    if (tr is None or not tr.exists()) and gz.exists():
                        tr = gz          # rebuild from an earlier pass's gzipped copy
                    if tr is None or not tr.exists():
                        per_stem[key].append(dict(record=rec["name"], uv3=False, why="trace not kept",
                                                  cache_setup=rec.get("cache_setup", "warm")))
                        continue
                    j = judge(rec, tr)
                    j["record"] = rec["name"]
                    j["cache_setup"] = rec.get("cache_setup", "warm")   # per record (random: per test)
                    if rec.get("cache_setup_mode"):
                        j["cache_setup_mode"] = rec["cache_setup_mode"]
                        j["cache_setup_seed"] = rec.get("cache_setup_seed")
                    per_stem[key].append(j)
                    td = dg / "traces" / mode; td.mkdir(parents=True, exist_ok=True)
                    if tr != gz:
                        with tr.open("rb") as fi, gzip.open(gz, "wb") as fo:
                            shutil.copyfileobj(fi, fo)
                except Exception:
                    L(f"ERROR {key} {rec['name']}:\n{traceback.format_exc()}")
                    per_stem[key].append(dict(record=rec["name"], uv3=False, why="exception"))
    out = {k: dict(uv3=all(v["uv3"] for v in vs), variants=vs) for k, vs in per_stem.items()}
    (dg / "uv3_rmw_evidence.json").write_text(json.dumps(out, indent=2) + "\n")
    n = sum(1 for v in out.values() if v["uv3"])
    L(f"hits judged: {len(out)}  uv3: {n}  not uv3: {len(out) - n}")
    by_cs = defaultdict(lambda: [0, 0])
    for v in out.values():
        cs = "+".join(sorted({x.get("cache_setup", "warm") for x in v["variants"]}))
        by_cs[cs][0] += 1
        by_cs[cs][1] += bool(v["uv3"])
    for cs, (nh, nu) in sorted(by_cs.items()):
        L(f"  cache_setup={cs}: hits {nh}  uv3 {nu}")
    for k, v in sorted(out.items()):
        if not v["uv3"]:
            L(f"  not-uv3 {k}: " + "; ".join(x["why"] for x in v["variants"] if not x["uv3"]))
    if not a.keep_workdirs:
        removed = 0
        for wd in sorted(workdirs):
            p = Path(wd)
            if p.name.startswith("gem5_") and p.parent == Path("/tmp") and p.exists():
                shutil.rmtree(p, ignore_errors=True); removed += 1
        L(f"removed {removed} kept gem5 workdirs (of {len(workdirs)} listed)")
    L("END")


if __name__ == "__main__":
    sys.exit(main())
