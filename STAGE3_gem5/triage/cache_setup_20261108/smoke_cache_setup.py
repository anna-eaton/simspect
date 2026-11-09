#!/usr/bin/env python3
"""Per-build smoke test of run_config gem5.cache_setup (2026-11-08, cache-setup session).

For each run config given, runs ONE test (default: the rmw_frame fixture, STT_6_rmw
inst-000003) warm and cold through gem5_common.process_one with the config's own
gem5 env (pipeline._build_gem5_env), and reports from the O3PipeView trace:
  * whether gem5 finished (status/error, panic text),
  * how many of the inserted clflush instructions retired,
  * issue->complete latency (cycles) of loads that read the flushed frame:
    the test-region load at __litmus_<stem>_pc2 (reads 48(%rsp)) and the
    epilogue `popq` loads (saved registers, always committed);
  * the number of SimSpect `L1D:fill` hook lines (hooked builds only);
  * verify: for every flushed line, hit or miss on its FIRST demand access after the
    last flush, at L1D and at the next level (classic builds: `Cache` debug flag;
    Ruby builds: `ProtocolTrace`, miss = the access starts from state NP/I; flushed
    line addresses also from the LSQUnit CleanInvalid packet lines, so a build whose
    cache ignores the flush shows up as hits). Flags added for the smoke run only.
A config may be given as <cfg>:<strategy> (default cold).

Usage (cafe2 gem5_dev, repo tree as cwd):
  python3 STAGE3_gem5/triage/cache_setup_20261108/smoke_cache_setup.py \
      --out <dir> runconfigs/footprint/run_config_STT_6_cleanupspec_footprint.jsonc ...
Writes <dir>/smoke.json and <dir>/smoke.log (start/end, per-run result, tracebacks).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FIX = REPO / "STAGE3_gem5" / "tests" / "fixtures" / "cache_setup" / "rmw_frame"

CHILD = r'''
import json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1] + "/STAGE3_gem5")
import gem5_common as gc, check_ld
s, a = Path(sys.argv[2]), Path(sys.argv[3])
gc._scheme = int(sys.argv[4])
CLS = re.compile(r"^\s*(\d+): system\.(cpu\.dcache|l2): (?:access for )?(\w+) \[([0-9a-f]+):[0-9a-f]+\][^\n]*?\b(hit|miss)\b")
LSQF = re.compile(r"^\s*(\d+): system\.cpu\.iew\.lsq.*pkt: CleanInvalid\w* \[([0-9a-f]+):")
RUBY = re.compile(r"^\s+(\d+)\s+\d+\s+(Seq|L0Cache|L1Cache|L2Cache)\s+(\S+)\s+(\S*)\s+\[0x([0-9a-f]+), line 0x([0-9a-f]+)\](.*)$")
NONDEMAND = ("Clean", "Write", "Writeback", "Upgrade", "Flush", "Inv", "Evict")
def verify(txt):
    """Per flushed line: hit or miss on its FIRST demand access after the last flush."""
    cls, rub, lsq = [], [], []
    for ln in txt.splitlines():
        m = LSQF.match(ln)
        if m:
            lsq.append((int(m.group(1)), int(m.group(2), 16) & ~63))
            continue
        m = CLS.match(ln)
        if m:
            cls.append((int(m.group(1)), m.group(2), m.group(3), int(m.group(4), 16) & ~63, m.group(5)))
            continue
        m = RUBY.match(ln)
        if m:
            rub.append((int(m.group(1)), m.group(2), m.group(3), m.group(4), int(m.group(6), 16), m.group(7)))
    res = {}
    if cls:
        fl = [(e[0], e[3]) for e in cls if e[1] == "cpu.dcache" and e[2] == "CleanInvalidReq"] + lsq
        if not fl:
            return dict(kind="classic", note="no CleanInvalidReq seen")
        tend = max(e[0] for e in fl); lines = {e[1] for e in fl}
        for lvl in ("cpu.dcache", "l2"):
            first = {}
            for e in cls:
                if e[0] > tend and e[1] == lvl and e[3] in lines and e[3] not in first \
                   and not e[2].startswith(NONDEMAND):
                    first[e[3]] = e[4]
            res[lvl] = dict(flushed=len(lines), touched=len(first),
                            miss=sum(v == "miss" for v in first.values()),
                            hit=sum(v == "hit" for v in first.values()))
        return dict(kind="classic", **res)
    if rub:
        seqf = [(e[0], e[4]) for e in rub if e[1] == "Seq" and e[2] == "Begin" and "FLUSH" in e[5]]
        fl = seqf + lsq
        if not fl:
            return dict(kind="ruby", note="no FLUSH and no CleanInvalid packet seen")
        tend = max(e[0] for e in fl); lines = {e[1] for e in fl}
        res["ruby_flush_requests"] = len(seqf)
        inner = "L0Cache" if any(e[1] == "L0Cache" for e in rub) else "L1Cache"
        outer = "L1Cache" if inner == "L0Cache" else "L2Cache"
        for lvl in (inner, outer):
            first = {}
            for e in rub:
                if e[0] > tend and e[1] == lvl and e[4] in lines and e[4] not in first \
                   and not e[2].startswith(("Flush", "WB", "Data", "Mem", "Ack", "Inv", "PUT",
                                            "Exclusive", "Unblock", "Fwd", "L1_Replacement",
                                            "L2_Replacement", "L0_Replacement", "WB_Ack",
                                            "Writeback", "L1_PUTX", "Mem_Ack")):
                    first[e[4]] = (e[2], e[3].split(">")[0])
            miss = sum(1 for ev, st in first.values() if st in ("NP", "I"))
            res[lvl] = dict(flushed=len(lines), touched=len(first), miss=miss,
                            hit=len(first) - miss,
                            events=sorted({f"{ev}:{st}" for ev, st in first.values()})[:8])
        return dict(kind="ruby", **res)
    return dict(kind="none", note="no Cache/ProtocolTrace lines (add the debug flag)")
r = gc.process_one(s, a, check_ld.check_ld, keep_tmp=True)
out = dict(status=r.get("status"), error=(r.get("error") or "")[:300],
           cache_setup=r.get("cache_setup"), info=r.get("cache_setup_info"))
wd = Path(r["workdir"]); out["workdir"] = str(wd)
binary = wd / s.stem
trace = wd / "m5out" / gc.GEM5_DBG_FILE
if trace.exists():
    by_pc = gc.parse_pipeview(trace)
    tpc = gc.parse_ticks_per_cycle(wd / "m5out")
    nm = {l.split()[2]: int(l.split()[0], 16) for l in subprocess.check_output(
        ["nm", "--defined-only", str(binary)], text=True).splitlines() if len(l.split()) == 3}
    rows = gc._disasm(binary)
    safe = s.stem.replace("-", "_")
    def lat(pc):
        recs = [x for x in by_pc.get(pc, []) if x.get("issue") and x.get("complete")]
        return [round((x["complete"] - x["issue"]) / tpc) for x in recs]
    tgt = nm.get(f"__litmus_{safe}_pc2")
    out["pc2_load_lat"] = lat(tgt) if tgt else None
    out["pop_lat"] = [l for row in rows if row[2].startswith("pop") for l in lat(row[0])]
    b, e = nm.get("__simspect_cachesetup_begin"), nm.get("__simspect_cachesetup_end")
    if b is not None:
        fl = [row[0] for row in rows if b <= row[0] < e and row[2].startswith("clflush")]
        out["clflush_n"] = len(fl)
        out["clflush_retired"] = sum(1 for pc in fl if any(x.get("retire") for x in by_pc.get(pc, [])))
        out["clflush_lat"] = sorted({l for pc in fl for l in lat(pc)})[:5]
    txt = trace.read_text(errors="replace")
    out["l1d_fill_lines"] = txt.count("L1D:fill")
    out["verify"] = verify(txt)
print("RESULT " + json.dumps(out))
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("configs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--s", nargs="+", default=[str(next(FIX.glob("inst-*.s"))), str(next(
        (FIX.parent / "recon_redzone").glob("inst-*.s")))])
    a = ap.parse_args()
    sys.path.insert(0, str(REPO))
    import pipeline
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "smoke.log").open("a")

    def L(m):
        line = f"{time.strftime('%F %T')} {m}"
        print(line, flush=True); log.write(line + "\n"); log.flush()

    L(f"START tests={a.s} configs={a.configs}")
    res = {}
    for spec, s in [(c, Path(x)) for c in a.configs for x in a.s]:
        ann = s.parent / f"{s.stem}.ann.json"
        cfgp, _, strat = spec.partition(":")
        cfg = pipeline.load_config(Path(cfgp))
        g0 = cfg["gem5"]
        for mode in ("warm", strat or "cold"):
            g = dict(g0); g["cache_setup"] = mode
            # per-line hit/miss evidence: Ruby ProtocolTrace / classic Cache debug flag
            g["debug_flags"] = list(dict.fromkeys(list(g0.get("debug_flags") or ["O3PipeView"])
                                                 + ["Cache", "ProtocolTrace", "LSQUnit"]))
            env = dict(os.environ)
            for k in [k for k in env if k.startswith("SIMSPECT_")]:
                del env[k]
            env.update(pipeline._build_gem5_env(g, cfg.get("speculation", {})))
            try:
                p = subprocess.run([sys.executable, "-c", CHILD, str(REPO), str(s), str(ann),
                                    str(cfg["gem5"].get("scheme", 2))],
                                   env=env, capture_output=True, text=True, timeout=900)
                line = next((l for l in p.stdout.splitlines() if l.startswith("RESULT ")), None)
                r = json.loads(line[7:]) if line else dict(status="harness_error",
                                                            error=(p.stderr or p.stdout)[-1500:])
            except Exception:
                r = dict(status="harness_error", error=traceback.format_exc())
            res[f"{Path(cfgp).name}|{s.parent.name}|{mode}"] = r
            L(f"{Path(cfgp).name} {s.parent.name} {mode}: {json.dumps(r)[:900]}")
    (out / "smoke.json").write_text(json.dumps(res, indent=1))
    L(f"END -> {out / 'smoke.json'}")


if __name__ == "__main__":
    main()
