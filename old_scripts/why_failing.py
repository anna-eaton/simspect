#!/usr/bin/env python3
"""
why_failing.py — classify NON-hit ld grid-points by failure mode.

For each ld test's grid points that did NOT trigger, figure out why:

  A.  xmit never reached complete (xmit_complete == 0)
        A1. xmit never even issued (xmit_issue == 0)
              → load got squashed in fetch/decode/dispatch
        A2. xmit issued but didn't complete
              → squashed during execute, or dependency stall ate the window
  B.  load completed too EARLY (xmit_complete <= lc_retire)
        → the load was on the architectural path, not the speculative one
  C.  load completed too LATE (xmit_complete >= fnc_retire)
        → branch resolved before load finished its work
  D.  status != ok (gem5 / linker / parse error)

Per-test summary: every ld test contributes its BEST grid-point (the
closest to triggering by xmit_complete falling inside the window).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT      = Path(__file__).parent
MODEL     = sys.argv[1] if len(sys.argv) > 1 else "STT_6"
KIND      = sys.argv[2] if len(sys.argv) > 2 else "ld"
ANN_DIR   = ROOT / "generated" / MODEL / "ann"
SWEEP     = ROOT / "generated" / MODEL / "sweep"
RAW_DIR   = SWEEP / "raw_results"


def classify(row: dict) -> str:
    if row.get("status") not in ("ok", None):
        return "D_error"
    xc  = row.get("xmit_complete") or 0
    xi  = row.get("xmit_issue")    or 0
    lc  = row.get("lc_retire")     or 0
    fnc = row.get("fnc_retire")    or 0
    if row.get("issued_in_window"):
        return "HIT"
    if xc == 0:
        if xi == 0:
            return "A1_no_issue"
        return "A2_no_complete"
    if lc > 0 and xc <= lc:
        return "B_pre_window"
    if fnc > 0 and xc >= fnc:
        return "C_post_window"
    return "?_unknown"


def main() -> None:
    print(f"loading xmit kinds from {ANN_DIR} …")
    xmit_kind = {}
    for ap in ANN_DIR.glob("*.ann.json"):
        try:
            a = json.loads(ap.read_text())
        except Exception:
            continue
        stem = ap.stem.replace(".ann", "")
        xmit_kind[stem] = (a.get("xmit") or {}).get("kind", "?")
    target_stems = {s for s, k in xmit_kind.items() if k == KIND}
    print(f"  {len(target_stems)} tests with xmit_kind={KIND}")

    # Stream raw_results, classify each row
    per_row_cat   = Counter()
    per_test_best = {}      # stem -> (priority, category) where lower priority = "closer to hit"
    PRIORITY = {"HIT": 0, "C_post_window": 1, "B_pre_window": 2,
                "A2_no_complete": 3, "A1_no_issue": 4,
                "D_error": 5, "?_unknown": 6}

    n_rows = 0
    for bf in sorted(RAW_DIR.glob("grid*_batch*.json")):
        try:
            rows = json.loads(bf.read_text())
        except Exception:
            continue
        for r in rows:
            stem = r.get("name")
            if stem not in target_stems: continue
            n_rows += 1
            cat = classify(r)
            per_row_cat[cat] += 1
            pri = PRIORITY.get(cat, 99)
            if stem not in per_test_best or per_test_best[stem][0] > pri:
                per_test_best[stem] = (pri, cat)

    print(f"\n{KIND} variant-rows scanned: {n_rows}")
    print(f"{KIND} tests with any data:    {len(per_test_best)}")

    print(f"\n── PER-ROW (variant-runs) classification ──")
    total = sum(per_row_cat.values())
    for cat in ["HIT", "A1_no_issue", "A2_no_complete",
                "B_pre_window", "C_post_window", "D_error", "?_unknown"]:
        n = per_row_cat.get(cat, 0)
        if n:
            print(f"  {cat:<18} {n:>8}  ({100*n/total:>5.2f}%)")

    print(f"\n── PER-TEST best-grid-point classification ──")
    per_test_cat = Counter(v[1] for v in per_test_best.values())
    t_total = sum(per_test_cat.values())
    for cat in ["HIT", "A1_no_issue", "A2_no_complete",
                "B_pre_window", "C_post_window", "D_error", "?_unknown"]:
        n = per_test_cat.get(cat, 0)
        if n:
            print(f"  {cat:<18} {n:>8}  ({100*n/t_total:>5.2f}%)")

    # For the dominant failure category, dump a few example stems
    failure_cats = ["A1_no_issue", "A2_no_complete", "B_pre_window",
                    "C_post_window"]
    print(f"\n── sample failing stems by category ──")
    by_cat = defaultdict(list)
    for stem, (_, cat) in per_test_best.items():
        if cat in failure_cats:
            by_cat[cat].append(stem)
    for cat in failure_cats:
        if by_cat[cat]:
            print(f"  {cat}: {len(by_cat[cat])} tests; first 5: "
                  f"{by_cat[cat][:5]}")


if __name__ == "__main__":
    main()
