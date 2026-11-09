#!/usr/bin/env python3
"""summarize_stt.py (STT agent 2026-11-09): runs.log -> one table row per command: file, label, expected
(from the __SAT/__UNSAT/__info suffix of the label), actual, ms, OK/MISMATCH."""
import re, sys
from pathlib import Path
L = Path(__file__).resolve().parent / "runs.log"
cur = None
rows = []
for line in L.read_text().splitlines():
    m = re.match(r"\S+ \S+ (\S+\.als)(?: \[dump\])? rc=(\d+) secs=(\d+)", line)
    if m:
        cur = (m.group(1), m.group(2), m.group(3)); continue
    m = re.match(r"CMD (\S+) (SAT|UNSAT|COUNT|DUMPED)\s*(.*)", line)
    if m and cur:
        label, res, rest = m.groups()
        exp = "SAT" if label.endswith("__SAT") else "UNSAT" if label.endswith("__UNSAT") else ""
        if res in ("COUNT", "DUMPED"):
            n, st, ms = rest.split()
            act, ms = f"{res.lower()} {n} {st.lower()}", ms
        else:
            act, ms = res, rest.strip()
        ok = "" if not exp else ("OK" if exp == act else "MISMATCH")
        rows.append((cur[0], label, exp, act, f"{int(ms)/1000:.1f}s", ok))
for r in rows:
    print(" | ".join(r))
