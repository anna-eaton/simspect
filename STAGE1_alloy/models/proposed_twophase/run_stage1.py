#!/usr/bin/env python3
"""run_stage1.py — unattended Stage-1 (core) enumeration of ONE draft two-phase model.

DRAFT TOOLING (2026-11-03). Output is for review only: it must not feed any
production testset until Anna signs off (wiki/design/TWO_PHASE_MODELS.md).

Runs the repo's own driver exactly as pipeline.py:phase_xml does
(`java -cp alloy6.jar:. a6CountModels <model> <out_dir> <cap>`, cwd STAGE1_alloy),
under a wall-clock timeout, and writes a careful log:
  start/end time, exact command, model sha256, scope line, free disk, instance-count
  progress every --poll seconds, the verdict (EXHAUSTED = solver reached UNSAT below
  the cap; CAPPED; TIMEOUT; DISK_GUARD; ERROR), and the full stdout/stderr of java.
Disk guard: refuses to start under --min-free-start GB free; kills java and stops
if free space drops under --min-free-run GB. Output only under testsets/ (gitignored).

Usage (one per model; see TWO_PHASE_MODELS.md "Runs" for the exact launches):
  nohup python3 run_stage1.py --name STT_6 --model ../STT_6_core.als \
      --out ../../../testsets/STT_6__twophase_draft/stage1_xml \
      --log ~/Library/Logs/simspect/twophase_STT_6.log &
"""
import argparse
import datetime as dt
import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE1 = HERE.parent.parent            # STAGE1_alloy/
# Portable paths (2026-11-08): the Mac defaults are kept when they exist, so local runs are
# unchanged; on cafe2's gem5_dev container (Java 17 at /usr/bin/java) they fall back to
# `java` on PATH and the disk holding STAGE1_alloy. Override with SIMSPECT_JAVA / SIMSPECT_DISK.
_MAC_JAVA = "/opt/homebrew/opt/openjdk@17/bin/java"
_MAC_DISK = "/System/Volumes/Data"
JAVA = os.environ.get("SIMSPECT_JAVA") or (_MAC_JAVA if os.path.exists(_MAC_JAVA) else (shutil.which("java") or "java"))
DISK = os.environ.get("SIMSPECT_DISK") or (_MAC_DISK if os.path.exists(_MAC_DISK) else str(STAGE1))


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def free_gb():
    return shutil.disk_usage(DISK).free / 1e9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--cap", type=int, default=100000,
                    help="instance cap (= alloy.max_instances in runconfigs/*.jsonc)")
    ap.add_argument("--timeout", type=int, default=6 * 3600, help="wall-clock seconds")
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--xmx", default="4g", help="JVM max heap (3 runs in parallel on an 18 GB Mac)")
    ap.add_argument("--min-free-start", type=float, default=50.0)
    ap.add_argument("--min-free-run", type=float, default=40.0)
    a = ap.parse_args()

    model = Path(a.model).resolve()
    out = Path(a.out).resolve()
    logp = Path(os.path.expanduser(a.log))
    logp.parent.mkdir(parents=True, exist_ok=True)
    log = open(logp, "a", buffering=1)

    def L(msg):
        log.write(f"{now()} [{a.name}] {msg}\n")

    L("=" * 70)
    L(f"START pid={os.getpid()} host={os.uname().nodename}")
    try:
        raw = model.read_bytes()
        L(f"model={model}")
        L(f"model_sha256={hashlib.sha256(raw).hexdigest()}")
        scope = [l for l in raw.decode().splitlines() if l.startswith("} for ")]
        L(f"scope_line={scope[0] if scope else '??'}")
        L(f"out_dir={out} cap={a.cap} timeout_s={a.timeout} xmx={a.xmx} poll_s={a.poll}")
        fg = free_gb()
        L(f"disk_free_GB={fg:.1f} (start needs >= {a.min_free_start}, stop if < {a.min_free_run})")
        if fg < a.min_free_start:
            L("VERDICT=NOT_STARTED reason=disk_free_below_start_threshold")
            return 2
        if out.exists() and any(out.glob("inst-*.xml")):
            L(f"VERDICT=NOT_STARTED reason=output_dir_not_empty ({out}); delete it to rerun")
            return 3
        out.mkdir(parents=True, exist_ok=True)
        cmd = [JAVA, f"-Xmx{a.xmx}", "-cp", "alloy6.jar:.", "a6CountModels",
               str(model), str(out), str(a.cap)]
        L(f"cwd={STAGE1}")
        L(f"cmd={' '.join(cmd)}")
        so = open(out / "_java_stdout.txt", "w")
        se = open(out / "_java_stderr.txt", "w")
        t0 = time.time()
        p = subprocess.Popen(cmd, cwd=STAGE1, stdout=so, stderr=se)
        L(f"java_pid={p.pid}")
        verdict = None
        last_n = -1
        while True:
            try:
                rc = p.wait(timeout=a.poll)
                break
            except subprocess.TimeoutExpired:
                pass
            n = sum(1 for _ in out.glob("inst-*.xml"))
            fg = free_gb()
            el = int(time.time() - t0)
            if n != last_n or el % (10 * a.poll) < a.poll:
                L(f"progress elapsed_s={el} instances={n} disk_free_GB={fg:.1f}")
                last_n = n
            if fg < a.min_free_run:
                verdict = "DISK_GUARD"
                L(f"disk free {fg:.1f} GB < {a.min_free_run} GB: killing java")
                p.kill(); rc = p.wait(); break
            if el >= a.timeout:
                verdict = "TIMEOUT"
                L(f"timeout {a.timeout}s reached: killing java (instances so far are kept)")
                p.kill(); rc = p.wait(); break
        so.close(); se.close()
        n = sum(1 for _ in out.glob("inst-*.xml"))
        stdout = (out / "_java_stdout.txt").read_text(errors="replace")
        stderr = (out / "_java_stderr.txt").read_text(errors="replace")
        if verdict is None:
            if rc != 0:
                verdict = "ERROR"
            elif "Total models:" in stdout and n < a.cap:
                verdict = "EXHAUSTED"   # solver returned UNSAT below the cap
            elif n >= a.cap:
                verdict = "CAPPED"
            else:
                verdict = "UNKNOWN"
        L(f"java_rc={rc} instances={n} elapsed_s={int(time.time() - t0)}")
        L(f"java_stdout: {stdout.strip()[-2000:]}")
        if stderr.strip():
            L("java_stderr (full):\n" + stderr)
        L(f"VERDICT={verdict}")
        return 0 if verdict in ("EXHAUSTED", "CAPPED") else 1
    except Exception:
        import traceback
        L("EXCEPTION:\n" + traceback.format_exc())
        L("VERDICT=ERROR")
        return 1
    finally:
        L(f"END pid={os.getpid()}")
        log.close()


if __name__ == "__main__":
    sys.exit(main())
