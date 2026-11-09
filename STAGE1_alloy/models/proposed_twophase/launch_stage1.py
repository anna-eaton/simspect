#!/usr/bin/env python3
"""launch_stage1.py — run every Stage-1 partition of every family in parallel, unattended.

DRAFT TOOLING (2026-11-08, simspect-c8). Runs inside a workspace laid out as
  <ws>/STAGE1_alloy/{alloy6.jar, a6CountModels.class, models/proposed_twophase/run_stage1.py}
  <ws>/parts/<family>/{partitions.json, <family>__<part>.als}   (from partition_stage1.py)
and, for each partition, calls run_stage1.py (wall-clock timeout, disk guard, full java
stdout/stderr, VERDICT line) with
  --out <ws>/out/<family>/<part>/stage1_xml   --log <ws>/logs/<family>__<part>.log
Big partitions (k6, then k5) start first. At most --jobs run at once.

Every --status-every seconds it rewrites <ws>/status/stage1_status.json (read by the
dashboard's Eval manifest page): per partition state / verdict / instances / elapsed,
per-family totals, and host load / memory / disk with a CONTENTION flag (load above
--max-load-frac of the cores, available memory under --min-mem-gb, or free disk under
--min-disk-gb). Launcher events go to <ws>/logs/launcher.log.

Usage (inside the gem5_dev container, in tmux):
  python3 <ws>/STAGE1_alloy/models/proposed_twophase/launch_stage1.py --ws <ws> \
      --families STT_6_core_ri Recon_6_core_ri SPT_6_oneLP_v2_core_ri Recon_6_stl_core STT_6_stl_core \
      --jobs 48 --cap 200000 --timeout 86400 --xmx 8g
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def mem_available_gb():
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1e6
    except OSError:
        pass
    return None


def parse_log(logp):
    """Last progress count + verdict from a run_stage1.py log."""
    st = {"instances": 0, "verdict": None, "elapsed_s": None}
    if not logp.exists():
        return st
    for line in logp.read_text(errors="replace").splitlines():
        m = re.search(r"instances=(\d+)", line)
        if m:
            st["instances"] = int(m.group(1))
        m = re.search(r"elapsed_s=(\d+)", line)
        if m:
            st["elapsed_s"] = int(m.group(1))
        m = re.search(r"VERDICT=(\w+)", line)
        if m:
            st["verdict"] = m.group(1)
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--families", nargs="+", required=True)
    ap.add_argument("--jobs", type=int, default=48)
    ap.add_argument("--cap", type=int, default=200000)
    ap.add_argument("--timeout", type=int, default=86400)
    ap.add_argument("--xmx", default="8g")
    ap.add_argument("--status-every", type=int, default=60)
    ap.add_argument("--max-load-frac", type=float, default=0.95)
    ap.add_argument("--min-mem-gb", type=float, default=40.0)
    ap.add_argument("--min-disk-gb", type=float, default=80.0)
    a = ap.parse_args()

    ws = Path(a.ws).resolve()
    runner = ws / "STAGE1_alloy/models/proposed_twophase/run_stage1.py"
    (ws / "logs").mkdir(exist_ok=True)
    (ws / "status").mkdir(exist_ok=True)
    llog = open(ws / "logs/launcher.log", "a", buffering=1)

    def L(msg):
        llog.write(f"{now()} {msg}\n")

    queue = []
    for fam in a.families:
        pj = json.loads((ws / "parts" / fam / "partitions.json").read_text())
        for p in pj["partitions"]:
            rank = (-p["k"], 0 if p["fact"] and "not in" not in p["fact"] else 1)
            queue.append({"family": fam, "part": p["name"], "k": p["k"], "fact": p["fact"],
                          "model": str(ws / "parts" / fam / p["file"]), "sha256": p["sha256"],
                          "out": str(ws / "out" / fam / p["name"] / "stage1_xml"),
                          "log": str(ws / "logs" / f"{fam}__{p['name']}.log"),
                          "rank": rank, "state": "queued"})
    queue.sort(key=lambda j: j["rank"])
    L(f"START launcher pid={os.getpid()} host={os.uname().nodename} jobs={a.jobs} cap={a.cap} "
      f"timeout={a.timeout} xmx={a.xmx} partitions={len(queue)} families={a.families}")

    running = {}
    t_last = 0
    ncpu = os.cpu_count() or 1
    contention_was = False
    while True:
        # reap
        for key, (proc, job) in list(running.items()):
            rc = proc.poll()
            if rc is not None:
                job["state"] = "done"
                job["rc"] = rc
                job["ended"] = now()
                st = parse_log(Path(job["log"]))
                L(f"END {key} rc={rc} verdict={st['verdict']} instances={st['instances']}")
                del running[key]
        # launch
        while len(running) < a.jobs:
            nxt = next((j for j in queue if j["state"] == "queued"), None)
            if nxt is None:
                break
            key = f"{nxt['family']}__{nxt['part']}"
            cmd = [sys.executable, str(runner), "--name", key, "--model", nxt["model"],
                   "--out", nxt["out"], "--log", nxt["log"], "--cap", str(a.cap),
                   "--timeout", str(a.timeout), "--xmx", a.xmx, "--poll", "60",
                   "--min-free-start", str(a.min_disk_gb + 20), "--min-free-run", str(a.min_disk_gb)]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=open(nxt["log"] + ".stderr", "w"))
            nxt["state"] = "running"
            nxt["started"] = now()
            running[key] = (proc, nxt)
            L(f"LAUNCH {key} pid={proc.pid} k={nxt['k']} fact={nxt['fact']!r}")
        # status
        if time.time() - t_last >= a.status_every or not running:
            t_last = time.time()
            load1 = os.getloadavg()[0]
            mem = mem_available_gb()
            disk = shutil.disk_usage(ws).free / 1e9
            reasons = []
            if load1 > a.max_load_frac * ncpu:
                reasons.append(f"load {load1:.1f} > {a.max_load_frac:.2f}x{ncpu} cores")
            if mem is not None and mem < a.min_mem_gb:
                reasons.append(f"available memory {mem:.0f} GB < {a.min_mem_gb:.0f}")
            if disk < a.min_disk_gb:
                reasons.append(f"free disk {disk:.0f} GB < {a.min_disk_gb:.0f}")
            if reasons and not contention_was:
                L("CONTENTION " + "; ".join(reasons))
            contention_was = bool(reasons)
            parts, fams = [], {}
            for j in queue:
                st = parse_log(Path(j["log"])) if j["state"] != "queued" else {"instances": 0, "verdict": None, "elapsed_s": None}
                rec = {k: j.get(k) for k in ("family", "part", "k", "fact", "state", "started", "ended", "rc", "sha256", "out", "log")}
                rec.update(st)
                parts.append(rec)
                f = fams.setdefault(j["family"], {"partitions": 0, "done": 0, "running": 0, "queued": 0,
                                                  "instances": 0, "verdicts": {}})
                f["partitions"] += 1
                f[j["state"]] += 1
                f["instances"] += st["instances"] or 0
                if st["verdict"]:
                    f["verdicts"][st["verdict"]] = f["verdicts"].get(st["verdict"], 0) + 1
            status = {"updated": now(), "host": os.uname().nodename, "workspace": str(ws),
                      "stage": "Stage 1 (cores, RI-only, up to 6 instructions)",
                      "config": {"jobs": a.jobs, "cap": a.cap, "timeout_s": a.timeout, "xmx": a.xmx},
                      "host_load": {"load1": load1, "ncpu": ncpu, "mem_available_gb": mem, "disk_free_gb": disk,
                                    "contention": bool(reasons), "reasons": reasons},
                      "families": fams, "partitions": parts}
            tmp = ws / "status/stage1_status.json.tmp"
            tmp.write_text(json.dumps(status, indent=1))
            tmp.replace(ws / "status/stage1_status.json")
        if not running and not any(j["state"] == "queued" for j in queue):
            break
        time.sleep(5)
    L("END launcher: all partitions finished")


if __name__ == "__main__":
    main()
