#!/usr/bin/env python3
"""usage_pace.py — is this 5-hour usage window being used at a linear pace?

(simspect-c8, 2026-11-09, Anna: "check if the usage is too low for the linear of the window
remaining".) There is no usage API Claude can read, so this is a local proxy built from the Claude
Code transcripts on this Mac (~/.claude/projects/**/*.jsonl; other machines' sessions are not seen).

- Usage = every assistant message's `usage` (deduplicated by message id), weighted roughly by
  API price ratios: input 1, cache write 1.25, cache read 0.1, output 5 ("weighted tokens").
- Window ends come from the limit-hit API errors in the transcripts ("... limit · resets 6:50pm
  (America/Los_Angeles)"): each gives one window [reset - 5 h, reset). The weighted usage inside a
  window that hit the limit is a sample of the cap; CAP = median of those samples.
- The current window starts at the first message after the last known window end (chained forward
  in 5 h steps), so `elapsed` and `remaining` are exact when the chain is right.
- Verdict: expected = CAP * elapsed / 5 h. UNDER if used < 0.8 * expected (room to spend, so the
  pace cron may launch work), OVER if used > 1.0 * expected, else ON_PACE.

Prints one JSON object; appends one line per run to ~/Library/Logs/simspect/usage_pace.log.
Usage: python3 scripts/usage_pace.py [--days 4]
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
W = {"input_tokens": 1.0, "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1, "output_tokens": 5.0}
RESET_RE = re.compile(r"limit[^\"\\]{0,40}resets (\d{1,2})(?::(\d\d))?\s*(am|pm) \(America/Los_Angeles\)")
WIN = dt.timedelta(hours=5)


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=4.0)
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=a.days)
    msgs, resets = {}, set()
    for f in glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True):
        try:
            if dt.datetime.fromtimestamp(os.path.getmtime(f), dt.timezone.utc) < since:
                continue
            fh = open(f, errors="replace")
        except OSError:
            continue
        for line in fh:
            if '"usage"' not in line and "isApiErrorMessage" not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get("timestamp")
            if not t:
                continue
            t = ts(t)
            if t < since:
                continue
            if d.get("isApiErrorMessage"):
                m = RESET_RE.search(line)
                if m:
                    h, mi, ap_ = int(m.group(1)), int(m.group(2) or 0), m.group(3)
                    h = (h % 12) + (12 if ap_ == "pm" else 0)
                    lt = t.astimezone(PT)
                    r = lt.replace(hour=h, minute=mi, second=0, microsecond=0)
                    if r <= lt:
                        r += dt.timedelta(days=1)
                    resets.add(r.astimezone(dt.timezone.utc))
                continue
            msg = d.get("message") or {}
            u = msg.get("usage")
            if not u or msg.get("role") != "assistant":
                continue
            mid = msg.get("id") or d.get("uuid")
            msgs[mid] = (t, sum(W[k] * (u.get(k) or 0) for k in W))
    events = sorted(msgs.values())

    def used(lo, hi):
        return sum(w for t, w in events if lo <= t < hi)

    samples = [{"end": r.isoformat(), "weighted": round(used(r - WIN, r))} for r in sorted(resets)]
    cap = statistics.median([s["weighted"] for s in samples]) if samples else None
    # current window: chain forward from the last known end
    anchor = max([r for r in resets if r <= now], default=None)
    start = None
    if anchor is not None:
        cur = anchor
        while True:
            nxt = next((t for t, _ in events if t >= cur), None)
            if nxt is None or nxt > now:
                break
            start, cur = nxt, nxt + WIN
            if cur > now:
                break
    out = {"now": now.isoformat(), "metric": "weighted tokens (in 1, cache-write 1.25, cache-read 0.1, out 5)",
           "cap_samples": samples, "cap_estimate": cap}
    if start is None or cap is None:
        out["verdict"] = "UNKNOWN"
        out["why"] = "no limit-hit window found in the scanned days" if cap is None else "no current window"
    else:
        end = start + WIN
        elapsed = (now - start).total_seconds() / WIN.total_seconds()
        u = used(start, now)
        exp = cap * elapsed
        verdict = "UNDER" if u < 0.8 * exp else ("OVER" if u > exp else "ON_PACE")
        out.update({"window_start": start.astimezone(PT).isoformat(timespec="minutes"),
                    "window_end": end.astimezone(PT).isoformat(timespec="minutes"),
                    "elapsed_frac": round(elapsed, 3), "used": round(u), "expected_linear": round(exp),
                    "used_frac_of_cap": round(u / cap, 3), "verdict": verdict})
    print(json.dumps(out, indent=1))
    logd = Path(os.path.expanduser("~/Library/Logs/simspect"))
    logd.mkdir(parents=True, exist_ok=True)
    with open(logd / "usage_pace.log", "a") as lf:
        lf.write(json.dumps({k: out.get(k) for k in ("now", "window_start", "window_end", "elapsed_frac",
                                                     "used", "expected_linear", "cap_estimate", "verdict")}) + "\n")


if __name__ == "__main__":
    main()
