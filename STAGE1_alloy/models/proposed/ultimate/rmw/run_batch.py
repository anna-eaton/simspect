#!/usr/bin/env python3
"""Run a batch of scratch Alloy queries under the shared one-java lock.

usage: run_batch.py <batch-name>
Exits 75 at once (no java started) if the lock is held by another agent.
Holds the lock for the whole batch, never longer than BATCH_CAP seconds,
kills java on timeout, and always rmdirs the lock. Log: runs.log (append).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

S = Path(__file__).parent
# shared one-java lock; the 2026-11-09 runs used the session scratchpad agents/alloy.lock
LOCK = Path(os.environ.get("ALLOY_LOCK", str(S / "alloy.lock")))
ALLOY = Path("/Users/annaeaton/Documents/stanford/trippel/simspect/STAGE1_alloy")
LOG = S / "rmw_alloy_runs.log"
BATCH_CAP = 19 * 60

# (query, driver, limit, timeout_s)
BATCHES = {
    "A": [
        ("C3_stt6core_b3", "a6CountModels", 1000000, 180),
        ("C2_core_normws_b3", "a6CountModels", 1000000, 180),
        ("C1_core_pinned_b3", "a6CountModels", 1000000, 180),
        ("C3_stt6core_b4", "a6CountModels", 1000000, 240),
        ("C2_core_normws_b4", "a6CountModels", 1000000, 240),
        ("C1_core_pinned_b4", "a6CountModels", 1000000, 240),
        ("F1_pinned", "a6CountModels", 300, 180),
        ("F2_rmw_xm", "a6CountModels", 30, 120),
        ("F3_rmw_spec_nonxm", "a6CountModels", 30, 120),
        ("F4_rmw_committed", "a6CountModels", 30, 120),
        ("F6_spec_ld_then_spec_rmw_same_loc", "a6CountModels", 30, 120),
        ("F7_rmw_stl_source", "a6CountModels", 30, 120),
        ("F8_rmw_tainted_src", "a6CountModels", 30, 120),
    ],
    "B": [("F5_xm_rmw_memops_irrelevant", "a6CountOnly", 1, 900)],
    "C": [("C4_core_rmw_nonxm_b5", "a6CountOnly", 1, 900)],
    "D": [("C5_core_pinned_b5", "a6CountModels", 20000, 900)],
    "E": [("K1_core_memops_irrelevant_b4", "a6CountOnly", 1000000, 240),
          ("K2_core_inaddr_matters_b4", "a6CountOnly", 1000000, 240),
          ("F9_rmw_hits_xmit_line", "a6CountModels", 30, 180),
          ("K3_full_inaddr_matters", "a6CountOnly", 5, 420)],
}


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def main():
    batch = sys.argv[1]
    try:
        LOCK.mkdir()
    except FileExistsError:
        print("LOCK_BUSY", flush=True)
        sys.exit(75)
    t_batch = time.time()
    log(f"batch {batch}: lock acquired")
    try:
        for name, driver, limit, tmo in BATCHES[batch]:
            left = BATCH_CAP - (time.time() - t_batch)
            if left < 30:
                log(f"{name}: SKIPPED (batch cap reached)")
                continue
            tmo = min(tmo, int(left))
            model = S / "queries" / f"{name}.als"
            out = S / "out" / name
            out.mkdir(parents=True, exist_ok=True)
            cmd = ["java", "-Xmx6g", "-cp", "alloy6.jar:.", driver, str(model)]
            cmd += [str(out), str(limit)] if driver == "a6CountModels" else [str(limit)]
            t0 = time.time()
            p = subprocess.Popen(cmd, cwd=ALLOY, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
            try:
                so, se = p.communicate(timeout=tmo)
                rc = p.returncode
                verdict = "OK"
            except subprocess.TimeoutExpired:
                p.kill()
                so, se = p.communicate()
                rc = p.returncode
                verdict = "TIMEOUT"
            dt = time.time() - t0
            n = len(list(out.glob("inst-*.xml")))
            last = (so.strip().splitlines() or [""])[-1]
            err = (se.strip().splitlines() or [""])[-1][:300]
            log(f"{name}: {verdict} rc={rc} {dt:.1f}s files={n} stdout='{last}' stderr='{err}'")
    finally:
        os.rmdir(LOCK)
        log(f"batch {batch}: lock released after {time.time() - t_batch:.0f}s")


if __name__ == "__main__":
    main()
