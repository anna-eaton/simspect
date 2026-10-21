#!/usr/bin/env python3
"""
jobs_registry.py — the canonical SimSpect jobs manifest.

Append-only JSONL at jobs/manifest.jsonl. Each run (a testsetgen PRODUCER or a
testrun gem5 CONSUMER campaign) writes a "start" record when it launches and an
"end" record when it finishes; both share a job_id, so a reader reduces by
job_id with last-wins to recover current state. Append-only keeps it crash-safe:
a killed job simply never writes its "end" line, and the dashboard flags it
stale by checking whether its pid is still alive.

Writers: testsetgen.py, testrun.py, and the dashboard's launch button.
Reader:  dashboard.py (via load_jobs()).

Record schema (one JSON object per line):
    {"event":"start","job_id":..., "kind":"gen"|"sweep", "model":..., "config":...,
     "results_name":..., "pid":..., "argv":[...], "status":"running",
     "started_at":"YYYY-MM-DD HH:MM:SS", ...extra}
    {"event":"end",  "job_id":..., "status":"done"|"failed",
     "ended_at":"YYYY-MM-DD HH:MM:SS", ...extra}
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

from simspect_paths import JOBS_DIR, JOBS_MANIFEST


def _append(rec: dict) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    with open(JOBS_MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def record_start(kind: str, model: str, config, *,
                 results_name=None, extra: dict | None = None) -> str:
    """Record a job launch. Returns a job_id to hand back to record_end()."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    pid = os.getpid()
    job_id = f"{kind}-{model}-{ts}-{pid}"
    try:
        _append({
            "event": "start",
            "job_id": job_id,
            "kind": kind,                 # "gen" | "sweep"
            "model": model,
            "config": str(config),
            "results_name": results_name,
            "pid": pid,
            "argv": list(sys.argv),
            "status": "running",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            **(extra or {}),
        })
    except Exception:
        # Registry is best-effort instrumentation — never let it break a run.
        pass
    return job_id


def record_end(job_id: str, status: str = "done", *, extra: dict | None = None) -> None:
    try:
        _append({
            "event": "end",
            "job_id": job_id,
            "status": status,             # "done" | "failed"
            "ended_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            **(extra or {}),
        })
    except Exception:
        pass


def pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def load_jobs() -> list:
    """Reduce the append-only manifest into current per-job state (last-wins),
    newest first. Marks a job 'running' status as 'stale' if its pid is dead."""
    if not JOBS_MANIFEST.exists():
        return []
    jobs: dict = {}
    for line in JOBS_MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        jid = rec.get("job_id")
        if not jid:
            continue
        jobs.setdefault(jid, {}).update(rec)
    out = []
    for j in jobs.values():
        if j.get("status") == "running" and not pid_alive(j.get("pid")):
            j["status"] = "stale"
        out.append(j)
    return sorted(out, key=lambda j: j.get("started_at", ""), reverse=True)
