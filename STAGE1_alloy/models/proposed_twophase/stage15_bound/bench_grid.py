#!/usr/bin/env python3
"""bench_grid.py — run the Stage-1.5 bound/pin measurement grid (stage15-bound session, 2026-11-08).

For each job: make_s15_model.py builds a scratch model (production model + core seed + scope/IX/fold
edits), then a6Bench.java measures parse / Kodkod translation / CNF size / first instance /
instances in a fixed window / peak heap, under a hard wall-clock timeout.

Layout expected (mirrors the repo): <ws>/STAGE1_alloy/{stage_seed.py, alloy6.jar, models/<prod>.als,
models/proposed_twophase/stage15_bound/{make_s15_model.py, a6Bench.java, cores/}}.

Outputs (all under <ws>/bench/):
  models/<job>.als           the exact model each measurement ran
  out/<job>.stdout|stderr    full java output (BENCH/RESULT lines, any stack trace)
  dump/<job>/inst-*.txt      first --dump instances (for censuses)
  results.jsonl              one JSON line per finished job (resumable: finished jobs are skipped)
  bench.log                  start/end/verdict/errors of every job, with timestamps

Usage: python3 bench_grid.py --ws /tests/stage15_bound_20261108 --set main --jobs 6
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROD = {"STT_6": "STT_6.als", "Recon_6": "Recon_6.als", "SPT_6_oneLP_v2": "SPT_6_oneLP_v2.als"}
CORES = {
    "STT_6_ld": ("STT_6", "STT_6__k3_inst-000005.txt"),
    "STT_6_brx": ("STT_6", "STT_6__k3_inst-000008.txt"),
    "Recon_6_ld": ("Recon_6", "Recon_6__k3_inst-000005.txt"),
    "Recon_6_brx": ("Recon_6", "Recon_6__k3_inst-000011.txt"),
    "SPT_k3_ld": ("SPT_6_oneLP_v2", "SPT_6_oneLP_v2__k3_inst-000030.txt"),
    "SPT_k5_ld": ("SPT_6_oneLP_v2", "SPT_6_oneLP_v2__k5_Loads_inst-000003.txt"),
}


def jobs_for(which):
    J = []

    def add(core, n, pin, ops=0, states=0, query="none", ix="regen", fold="auto", enum=180, mini="prod", shape="any", ib=0):
        name = f"{core}__n{n}__pin{pin}__ops{ops or 9}" + (f"__st{states}" if states else "") + \
               (f"__{query}" if query != "none" else "") + (f"__ix{ix}" if ix != "regen" else "") + \
               (f"__fold{fold}" if fold != "auto" else "") + (f"__min{mini}" if mini != "prod" else "") + \
               (f"__{shape}" if shape != "any" else "") + (f"__int{ib}" if ib else "")
        J.append(dict(ib=ib, name=name, core=core, n=n, pin=pin, ops=ops, states=states, query=query, ix=ix,
                      fold=fold, enum=enum, mini=mini, shape=shape))

    if which == "main":
        for core in ("STT_6_ld", "Recon_6_ld", "SPT_k3_ld"):
            for pin in ("a", "b"):
                add(core, 6, pin)                 # production scope exactly
                add(core, 6, pin, ops=12)
                add(core, 7, pin, ops=14)
                add(core, 8, pin, ops=16)
                add(core, 10, pin, ops=20)
                add(core, 10, pin)                # bigger N but production 'for 9' operand cap
                add(core, 12, pin, ops=24)
    elif which == "queries":
        for core in ("STT_6_ld", "STT_6_brx", "Recon_6_ld", "SPT_k3_ld"):
            for n, ops in ((6, 0), (8, 16), (10, 20)):
                add(core, n, "b", ops=ops, query="splice_xm", enum=60)
            add(core, 8, "a", ops=16, query="splice_xm", enum=30)
        add("STT_6_ld", 10, "none", ops=20, query="fold_trunc", fold="keep", enum=30)
        add("STT_6_ld", 8, "none", ops=16, query="fold_trunc", fold="keep", enum=30)
        add("SPT_k3_ld", 8, "none", ops=16, query="fold_trunc", fold="keep", enum=30)
        add("Recon_6_ld", 10, "none", ops=20, query="fold_trunc", fold="keep", enum=30)
    elif which == "shapes":
        # s4-variant's S4 / A3c shapes under the Stage-1.5 designs (coordinator request 2026-11-08)
        for mini in ("prod", "leak_rs"):
            for n, ops in ((6, 0), (8, 16), (10, 20)):
                add("STT_6_ld", n, "b", ops=ops, query="s4_shape", enum=30, mini=mini)
                add("STT_6_brx", n, "b", ops=ops, query="a3c_shape", enum=30, mini=mini)
        add("STT_6_ld", 8, "a", ops=16, query="s4_shape", enum=30, mini="leak_rs")
        add("STT_6_brx", 8, "a", ops=16, query="a3c_shape", enum=30, mini="leak_rs")
    elif which == "minimality":
        for core in ("STT_6_ld", "SPT_k3_ld"):
            for n, ops in ((6, 0), (8, 16), (10, 20), (12, 24)):
                add(core, n, "b", ops=ops, mini="leak_rs")
    elif which == "explicit":
        # explicit (non-nested) protection-set fold: equivalence check, then cost at large N
        for core, n, ops in (("SPT_k3_ld", 6, 0), ("SPT_k3_ld", 8, 16), ("STT_6_ld", 6, 0), ("STT_6_ld", 10, 20),
                             ("Recon_6_ld", 8, 16)):
            add(core, n, "none", ops=ops, query="fold_equiv", fold="explicit", enum=10)
        for n in (8, 10, 12, 14, 16):
            add("SPT_k3_ld", n, "b", ops=2 * n, fold="explicit")
        add("SPT_k3_ld", 10, "a", ops=20, fold="explicit")
        add("SPT_k3_ld", 12, "a", ops=24, fold="explicit")
        add("SPT_k5_ld", 12, "b", ops=24, fold="explicit")
        add("STT_6_ld", 12, "b", ops=24, fold="explicit")
        add("STT_6_ld", 16, "b", ops=32, fold="explicit")
        add("SPT_k3_ld", 12, "b", ops=24, fold="explicit", query="splice_xm", enum=60)
        # OTB precursor (OTB_GENERATION_GAP.md:8) under the pins
        for core in ("STT_6_ld", "Recon_6_ld", "SPT_k3_ld"):
            for n, ops in ((6, 0), (8, 16), (10, 20)):
                add(core, n, "b", ops=ops, query="otb_shape", fold="explicit", enum=60)
            add(core, 8, "a", ops=16, query="otb_shape", fold="explicit", enum=30)
    elif which == "fixed":
        # re-measure with a 6-bit Int (the 4-bit default lets #-facts overflow once Operand scope > 9)
        for n, ops in ((6, 0), (8, 16), (10, 20), (12, 24)):
            add("STT_6_ld", n, "b", ops=ops, ib=6)
        add("STT_6_ld", 10, "a", ops=20, ib=6)
        add("SPT_k3_ld", 8, "b", ops=16, ib=6)
        add("SPT_k3_ld", 10, "b", ops=20, ib=6, fold="explicit")
        add("SPT_k3_ld", 12, "b", ops=24, ib=6, fold="explicit")
        for n, ops in ((10, 20), (12, 24)):
            add("STT_6_ld", n, "b", ops=ops, ib=6, shape="nospacer")
        add("SPT_k3_ld", 10, "b", ops=20, ib=6, fold="explicit", shape="nospacer")
        for n, ops in ((8, 16), (10, 20)):
            add("STT_6_ld", n, "b", ops=ops, ib=6, query="splice_xm", enum=60)
            add("STT_6_ld", n, "b", ops=ops, ib=6, query="otb_shape", enum=60)
        add("SPT_k3_ld", 8, "b", ops=16, ib=6, query="splice_xm", enum=60)
        add("SPT_k3_ld", 8, "b", ops=16, ib=6, query="otb_shape", enum=60)
        add("Recon_6_ld", 8, "a", ops=16, ib=6, query="otb_shape", enum=30)
        add("Recon_6_ld", 8, "b", ops=16, ib=6, query="otb_shape", enum=60)
        add("STT_6_ld", 8, "b", ops=16, ib=6, query="s4_shape", mini="leak_rs", enum=60)
        add("STT_6_brx", 8, "b", ops=16, ib=6, query="a3c_shape", mini="leak_rs", enum=60)
        add("STT_6_ld", 10, "none", ops=20, ib=6, query="fold_trunc", fold="keep", enum=30)
        add("SPT_k3_ld", 8, "none", ops=16, ib=6, query="fold_trunc", fold="keep", enum=30)
    elif which == "compact":
        # ban padding: does a bigger bound then give real (non-spacer) instructions / ALU ops on the path?
        for core in ("STT_6_ld", "SPT_k3_ld"):
            for n in (8, 10, 12):
                for shape in ("nospacer", "connected"):
                    add(core, n, "b", ops=2 * n, fold="explicit", shape=shape)
        add("STT_6_ld", 10, "b", ops=20, fold="explicit", shape="connected", query="otb_shape", enum=60)
        add("STT_6_brx", 10, "b", ops=20, fold="explicit", shape="connected", query="a3c_shape", mini="leak_rs", enum=60)
        add("STT_6_ld", 10, "b", ops=20, fold="explicit", shape="connected", query="s4_shape", mini="leak_rs", enum=60)
    elif which == "extra":
        for core in ("STT_6_ld", "SPT_k3_ld"):
            for n, ops in ((6, 0), (8, 16), (10, 20), (12, 24)):
                add(core, n, "c", ops=ops)
        add("STT_6_ld", 10, "b", ops=30)          # operand scope 3N
        add("STT_6_ld", 10, "b", ops=20, states=12)
        add("STT_6_ld", 10, "b", ops=20, ix="drop")
        add("SPT_k5_ld", 6, "a"); add("SPT_k5_ld", 8, "b", ops=16); add("SPT_k5_ld", 10, "b", ops=20)
        add("STT_6_brx", 6, "a"); add("STT_6_brx", 10, "b", ops=20)
        add("STT_6_ld", 14, "b", ops=28); add("STT_6_ld", 16, "b", ops=32)
        add("SPT_k3_ld", 14, "b", ops=28)
    else:
        sys.exit(f"unknown set {which}")
    return J


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--xmx", default="16g")
    ap.add_argument("--dump", type=int, default=300)
    ap.add_argument("--only", default="", help="regex filter on job names")
    a = ap.parse_args()

    ws = Path(a.ws).resolve()
    s1 = ws / "STAGE1_alloy"
    here = s1 / "models/proposed_twophase/stage15_bound"
    b = ws / "bench"
    for d in ("models", "out", "dump"):
        (b / d).mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    log = open(b / "bench.log", "a", buffering=1)

    def L(msg):
        with lock:
            log.write(f"{now()} {msg}\n")

    done = set()
    if (b / "results.jsonl").exists():
        for line in (b / "results.jsonl").read_text().splitlines():
            try:
                r = json.loads(line)
                if r.get("verdict") != "EXCEPTION":   # generator/setup failures are retried
                    done.add(r["name"])
            except Exception:
                pass
    jobs = [j for j in jobs_for(a.set) if j["name"] not in done and re.search(a.only, j["name"])]
    L(f"START set={a.set} pid={os.getpid()} jobs={len(jobs)} parallel={a.jobs} timeout={a.timeout} xmx={a.xmx}")

    def run(j):
        fam, core_file = CORES[j["core"]]
        model = b / "models" / f"{j['name']}.als"
        rec = dict(j, family=fam, core_file=core_file, started=now())
        t0 = time.time()
        try:
            gen = [sys.executable, str(here / "make_s15_model.py"), "--model", str(s1 / "models" / PROD[fam]),
                   "--core", str(here / "cores" / core_file), "--n", str(j["n"]), "--pin", j["pin"],
                   "--ix", j["ix"], "--fold", j["fold"], "--query", j["query"], "--minimality", j.get("mini", "prod"), "--shape", j.get("shape", "any"),
                   "--out", str(model)]
            if j["ops"]:
                gen += ["--operands", str(j["ops"])]
            if j.get("ib"):
                gen += ["--intbits", str(j["ib"])]
            if j["states"]:
                gen += ["--states", str(j["states"])]
            g = subprocess.run(gen, capture_output=True, text=True)
            if g.returncode != 0:
                raise RuntimeError(f"make_s15_model failed rc={g.returncode}: {g.stderr[-800:]}{g.stdout[-200:]}")
            L(f"RUN {j['name']}")
            cmd = ["timeout", str(a.timeout), "java", f"-Xmx{a.xmx}", "-cp", f"{s1}/alloy6.jar:{here}", "a6Bench",
                   str(model), str(j["enum"]), "100000", str(b / "dump" / j["name"]), str(a.dump)]
            with open(b / "out" / f"{j['name']}.stdout", "w") as so, open(b / "out" / f"{j['name']}.stderr", "w") as se:
                rc = subprocess.run(cmd, stdout=so, stderr=se).returncode
            out = (b / "out" / f"{j['name']}.stdout").read_text()
            rec["rc"] = rc
            m = re.search(r"^RESULT (.*)$", out, re.M)
            if m:
                for kv in m.group(1).split():
                    k, v = kv.split("=", 1)
                    try:
                        v = float(v) if "." in v else int(v)
                    except ValueError:
                        pass
                    rec[k] = v
            else:
                rec["verdict"] = "TIMEOUT" if rc == 124 else f"ERROR_rc{rc}"
                for key in ("translated", "first_result"):
                    mm = re.search(rf"event={key} t=([\d.]+)(.*)$", out, re.M)
                    if mm:
                        rec[f"{key}_t"] = float(mm.group(1))
                        rec[f"{key}_info"] = mm.group(2).strip()
                mm = re.search(r"event=translate_start t=([\d.]+)", out)
                if mm:
                    rec["translate_start_t"] = float(mm.group(1))
        except Exception as e:  # noqa: BLE001
            import traceback
            rec["verdict"] = "EXCEPTION"
            rec["error"] = traceback.format_exc()[-2000:]
            L(f"EXCEPTION {j['name']}: {e!r}")
        rec["wall_s"] = round(time.time() - t0, 1)
        rec["ended"] = now()
        with lock:
            with open(b / "results.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")
        L(f"END {j['name']} verdict={rec.get('verdict')} wall={rec['wall_s']}s inst={rec.get('instances')} "
          f"translate_s={rec.get('translate_s')} first_s={rec.get('first_s')}")
        if str(rec.get("verdict", "")).startswith(("ERROR", "EXCEPTION")):
            L(f"  see {b/'out'/(j['name']+'.stderr')}")

    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        list(pool.map(run, jobs))
    L(f"END set={a.set}")


if __name__ == "__main__":
    main()
