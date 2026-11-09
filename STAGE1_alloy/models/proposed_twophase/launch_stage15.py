#!/usr/bin/env python3
"""launch_stage15.py — Stage 1.5: pin every Stage-1 core into its production model, in parallel.

DRAFT TOOLING (2026-11-08, simspect-c8). For each family whose Stage 1 is complete (every
partition `done` in <ws>/status/stage1_status.json), every core <ws>/out/<core_fam>/<part>/
stage1_xml/inst-*.txt becomes one Alloy run of the PRODUCTION model (exactly 6 instructions,
its own minimality) with the structural seed `seed_core` from STAGE1_alloy/stage_seed.py
conjoined into `run gen_lit` (stage_pipeline.build_seeded_model). The production model text is
otherwise unchanged; seeded copies are written to <ws>/s15/<family>/models/.

Size (Anna, 2026-11-08): about --budget instances per family, split evenly over its cores:
per-core cap = max(1, ceil(budget / n_cores)). A core run stops at its cap, at --timeout, or
when Alloy exhausts (fewer instances than the cap = every flesh-out of that core).

Outputs:  <ws>/s15/<family>/out/<part>__<inst>/inst-*.{xml,txt} + _java_{stdout,stderr}.txt
          <ws>/s15/<family>/results.jsonl   one line per finished core (resumable: done cores skip)
          <ws>/status/stage15_status.json   rewritten every 60 s (dashboard), CONTENTION flag
          <ws>/logs/stage15_launcher.log
The same instance can come from two cores (it contains both); merge_stage15.py dedups.

Usage (inside the gem5_dev container, in tmux):
  python3 launch_stage15.py --ws /tests/simspect_alloy_20261108 --budget 300000 --jobs 40 \
     --family STT_6_stl=STT_6_stl_core:STAGE1_alloy/models/STT_6_stl.als  [--family ...]
"""
import argparse
import datetime as dt
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--family", action="append", required=True,
                    help="NAME=CORE_FAMILY:PRODUCTION_MODEL (model path relative to the workspace)")
    ap.add_argument("--budget", type=int, default=300000)
    ap.add_argument("--jobs", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=1800, help="wall-clock seconds per core run")
    ap.add_argument("--xmx", default="4g")
    ap.add_argument("--java", default=shutil.which("java") or "java")
    ap.add_argument("--min-disk-gb", type=float, default=60.0)
    ap.add_argument("--max-load-frac", type=float, default=0.95)
    ap.add_argument("--min-mem-gb", type=float, default=40.0)
    ap.add_argument("--limit-cores", type=int, default=0, help="testing only: run just the first N cores per family")
    ap.add_argument("--max-core-runs", type=int, default=0,
                    help="if a family has more cores than this (default = --budget), run a uniform random sample "
                         "of this many (seed --sample-seed) with per-core cap 1, and record it in PROVENANCE.json")
    ap.add_argument("--sample-seed", type=int, default=20261108)
    a = ap.parse_args()

    ws = Path(a.ws).resolve()
    stage1 = ws / "STAGE1_alloy"
    sys.path.insert(0, str(stage1))
    import stage_seed  # noqa: E402
    import stage_pipeline  # noqa: E402

    (ws / "logs").mkdir(exist_ok=True)
    (ws / "status").mkdir(exist_ok=True)
    llog = open(ws / "logs/stage15_launcher.log", "a", buffering=1)
    lock = threading.Lock()

    def L(msg):
        with lock:
            llog.write(f"{now()} {msg}\n")

    fams = {}
    for spec in a.family:
        name, rest = spec.split("=", 1)
        core_fam, model = rest.split(":", 1)
        fams[name] = {"core_fam": core_fam, "model": ws / model, "state": "waiting_for_stage1",
                      "cores": 0, "per_core": None, "done": 0, "running": 0, "instances": 0,
                      "verdicts": {}, "started": None, "ended": None}
    L(f"START stage15 launcher pid={os.getpid()} budget={a.budget} jobs={a.jobs} timeout={a.timeout} "
      f"families={ {k: (v['core_fam'], str(v['model'])) for k, v in fams.items()} }")

    def stage1_complete(core_fam):
        try:
            s = json.loads((ws / "status/stage1_status.json").read_text())
        except Exception:
            return False
        f = s.get("families", {}).get(core_fam)
        return bool(f) and f["done"] == f["partitions"]

    def run_core(fam, core_txt, part, per_core, flesh_text):
        key = f"{part}__{core_txt.stem}"
        fdir = ws / "s15" / fam
        out = fdir / "out" / key
        model = fdir / "models" / f"{key}.als"
        rec = {"core": str(core_txt), "key": key, "per_core": per_core}
        t0 = time.time()
        try:
            rels = stage_seed.parse_txt(str(core_txt))
            seed = stage_seed.build_pred(rels, "seed_core")
            model.write_text(stage_pipeline.build_seeded_model(flesh_text, seed))
            if out.exists():
                shutil.rmtree(out)
            out.mkdir(parents=True)
            cmd = [a.java, f"-Xmx{a.xmx}", "-cp", "alloy6.jar:.", "a6CountModels",
                   str(model), str(out), str(per_core)]
            with open(out / "_java_stdout.txt", "w") as so, open(out / "_java_stderr.txt", "w") as se:
                p = subprocess.Popen(cmd, cwd=stage1, stdout=so, stderr=se)
                try:
                    rc = p.wait(timeout=a.timeout)
                    timed_out = False
                except subprocess.TimeoutExpired:
                    p.kill()
                    rc = p.wait()
                    timed_out = True
            n = sum(1 for _ in out.glob("inst-*.xml"))
            stdout = (out / "_java_stdout.txt").read_text(errors="replace")
            if timed_out:
                verdict = "TIMEOUT"
            elif rc != 0:
                verdict = "ERROR"
            elif n >= per_core:
                verdict = "CAPPED"
            elif "Total models:" in stdout:
                verdict = "EXHAUSTED"
            else:
                verdict = "UNKNOWN"
            rec.update(instances=n, verdict=verdict, rc=rc)
        except Exception as e:  # noqa: BLE001
            import traceback
            rec.update(instances=0, verdict="ERROR", rc=None, error=traceback.format_exc()[-1500:])
            L(f"EXCEPTION {fam} {key}: {e!r}")
        rec["secs"] = int(time.time() - t0)
        rec["ended"] = now()
        with lock:
            with open(fdir / "results.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")
            F = fams[fam]
            F["done"] += 1
            F["running"] -= 1
            F["instances"] += rec["instances"]
            F["verdicts"][rec["verdict"]] = F["verdicts"].get(rec["verdict"], 0) + 1
        if rec["verdict"] in ("ERROR", "UNKNOWN"):
            L(f"{rec['verdict']} {fam} {key} rc={rec.get('rc')} (see {out}/_java_stderr.txt)")
        return rec

    pool = ThreadPoolExecutor(max_workers=a.jobs)
    pending = []
    ncpu = os.cpu_count() or 1
    contention_was = False
    t_status = 0
    while True:
        for fam, F in fams.items():
            if F["state"] == "waiting_for_stage1" and stage1_complete(F["core_fam"]):
                cores = sorted((ws / "out" / F["core_fam"]).glob("*/stage1_xml/inst-*.txt"))
                if a.limit_cores:
                    cores = cores[:a.limit_cores]
                n_all = len(cores)
                max_runs = a.max_core_runs or a.budget
                sampled = n_all > max_runs
                if sampled:
                    import random
                    cores = sorted(random.Random(a.sample_seed).sample(cores, max_runs))
                    L(f"FAMILY {fam}: {n_all} cores > {max_runs}: running a uniform sample of {max_runs} (seed {a.sample_seed})")
                F["cores"] = len(cores)
                F["per_core"] = max(1, math.ceil(a.budget / max(1, len(cores))))
                fdir = ws / "s15" / fam
                (fdir / "models").mkdir(parents=True, exist_ok=True)
                done_keys = set()
                if (fdir / "results.jsonl").exists():
                    for line in (fdir / "results.jsonl").read_text().splitlines():
                        try:
                            r = json.loads(line)
                        except ValueError:
                            continue
                        if r.get("verdict") in ("CAPPED", "EXHAUSTED", "TIMEOUT"):
                            done_keys.add(r["key"])
                            F["done"] += 1
                            F["instances"] += r["instances"]
                            F["verdicts"][r["verdict"]] = F["verdicts"].get(r["verdict"], 0) + 1
                flesh_text = F["model"].read_text()
                (fdir / "PROVENANCE.json").write_text(json.dumps({
                    "family": fam, "core_family": F["core_fam"], "production_model": str(F["model"]),
                    "production_model_sha256": __import__("hashlib").sha256(flesh_text.encode()).hexdigest(),
                    "cores": len(cores), "cores_total": n_all, "sampled": sampled, "sample_seed": a.sample_seed if sampled else None, "budget": a.budget, "per_core": F["per_core"],
                    "timeout_s": a.timeout, "seed_tool": "STAGE1_alloy/stage_seed.py + stage_pipeline.build_seeded_model",
                    "started": now()}, indent=1))
                F["state"] = "running"
                F["started"] = now()
                L(f"FAMILY {fam}: stage 1 complete, {len(cores)} cores, per-core cap {F['per_core']}, "
                  f"{len(done_keys)} already done")
                for c in cores:
                    part = c.parent.parent.name
                    if f"{part}__{c.stem}" in done_keys:
                        continue
                    with lock:
                        F["running"] += 1
                    pending.append(pool.submit(run_core, fam, c, part, F["per_core"], flesh_text))
        for fam, F in fams.items():
            if F["state"] == "running" and F["done"] >= F["cores"]:
                F["state"] = "done"
                F["ended"] = now()
                L(f"FAMILY {fam} done: {F['instances']} instances, verdicts {F['verdicts']}")
        all_done = all(F["state"] == "done" for F in fams.values())
        if time.time() - t_status >= 60 or all_done:
            t_status = time.time()
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
            status = {"updated": now(), "host": os.uname().nodename, "workspace": str(ws),
                      "stage": "Stage 1.5 (pin each core into the production model, exactly 6 instructions)",
                      "config": {"budget_per_family": a.budget, "jobs": a.jobs, "timeout_s": a.timeout, "xmx": a.xmx},
                      "host_load": {"load1": load1, "ncpu": ncpu, "mem_available_gb": mem, "disk_free_gb": disk,
                                    "contention": bool(reasons), "reasons": reasons},
                      "families": {k: {kk: (str(vv) if isinstance(vv, Path) else vv) for kk, vv in v.items()}
                                   for k, v in fams.items()}}
            tmp = ws / "status/stage15_status.json.tmp"
            tmp.write_text(json.dumps(status, indent=1))
            tmp.replace(ws / "status/stage15_status.json")
            if disk < a.min_disk_gb:
                L("DISK GUARD: stopping new core runs")
                for fu in pending:
                    fu.cancel()
                break
        if all_done:
            break
        time.sleep(10)
    pool.shutdown(wait=True)
    L("END stage15 launcher")


if __name__ == "__main__":
    main()
