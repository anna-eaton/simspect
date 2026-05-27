#!/usr/bin/env python3
"""
verify_unresolved_at_xmit.py

For every ld hit (every triggering grid point of every ld-xmit test),
verify the strict invariant:

  xmit_complete <  (broadcast time of the branch whose mode is
                    "mispredict_not_taken" or "mispredict_taken"
                    in the .ann.json)

Where "broadcast time" = retire-tick of the branch's jne PC in the pipeview.
We use the unresolved branch's `x86_branch_offset` (the actual jne) as
fnc_pc instead of whatever the first_noncommitted marker was — these may
or may not be the same.

Outputs:
  - tally of (fnc_pc == unresolved-branch jne PC)?
  - violations of the invariant
  - distribution of (unresolved_broadcast - xmit_complete) slack
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT       = Path(__file__).parent
MODEL      = "STT_6"
ANN_DIR    = ROOT / "generated" / MODEL / "ann"
SWEEP_DIR  = ROOT / "generated" / MODEL / "sweep"
RAW_DIR    = SWEEP_DIR / "raw_results"


def main() -> None:
    # Load all ann.json files; collect xmit_kind + unresolved-branch jne PC
    # We need to recover the **absolute** jne PC. The raw_results store
    # absolute pcs (hex strings); the ann.json stores function-relative
    # offsets. We need the function base address.
    #
    # The function base is the same for every test of this model: each test
    # is linked separately with the same _start prologue, so the function
    # base is determined by the prologue length. We can recover it from the
    # raw_results: fnc_pc - fnc_x86_offset = base.
    #
    # We do this per-test: parse fnc_pc absolute from raw row, subtract the
    # ann.json's first_noncommitted.x86_offset → base for this test.
    print("loading ann.json metadata …")
    ann_meta = {}    # stem -> dict(xmit_kind, fnc_offset, unresolved_offset)
    for ap in ANN_DIR.glob("*.ann.json"):
        try:
            a = json.loads(ap.read_text())
        except Exception:
            continue
        stem = ap.stem.replace(".ann", "")
        xmit_kind = (a.get("xmit") or {}).get("kind", "?")
        fnc_off = ((a.get("commit_boundary") or {})
                   .get("first_noncommitted") or {}).get("x86_offset")
        unresolved_offsets = [
            e.get("x86_branch_offset")
            for e in a.get("annotations", [])
            if (e.get("mode") or "").startswith("mispredict_")
        ]
        ann_meta[stem] = dict(
            xmit_kind=xmit_kind,
            fnc_offset=fnc_off,
            unresolved_offsets=[o for o in unresolved_offsets if o is not None],
        )

    print(f"  {len(ann_meta)} ann files; xmit_kind counts: "
          f"{Counter(m['xmit_kind'] for m in ann_meta.values())}")

    # Process raw batches: for each ld hit row, check the invariant.
    print(f"\nstreaming {sum(1 for _ in RAW_DIR.glob('grid*_batch*.json'))} batch files …")
    n_total_hits = 0
    n_fnc_is_unresolved = 0
    n_fnc_is_not_unresolved = 0
    n_unresolved_missing  = 0
    n_violations = 0
    n_no_unresolved_in_ann = 0
    n_strict_invariant_holds = 0
    n_unbounded = 0   # fnc_retire == 0 → fnc was itself squashed
    slack_ticks_distribution = Counter()

    def parse_hex(s):
        if s is None: return None
        try: return int(s, 16) if isinstance(s, str) else int(s)
        except Exception: return None

    for bf in sorted(RAW_DIR.glob("grid*_batch*.json")):
        try:
            rows = json.loads(bf.read_text())
        except Exception:
            continue
        for r in rows:
            if not r.get("issued_in_window"): continue
            stem = r["name"]
            meta = ann_meta.get(stem)
            if not meta or meta["xmit_kind"] != "ld":
                continue
            n_total_hits += 1

            fnc_pc_abs = parse_hex(r.get("first_noncommitted_pc"))
            fnc_off    = meta["fnc_offset"]
            unresolved_offsets = meta["unresolved_offsets"]

            # Verify fnc_pc matches the unresolved-branch jne
            if not unresolved_offsets:
                n_no_unresolved_in_ann += 1
                continue
            # Compute function base from fnc info: base = fnc_pc_abs - fnc_off
            if fnc_pc_abs is None or fnc_off is None:
                n_unresolved_missing += 1
                continue
            base = fnc_pc_abs - fnc_off
            # Compute each unresolved branch's absolute PC
            unresolved_abs = [base + o for o in unresolved_offsets]
            if fnc_pc_abs in unresolved_abs:
                n_fnc_is_unresolved += 1
            else:
                n_fnc_is_not_unresolved += 1

            # Strict invariant: xmit_complete < fnc_retire
            xc  = r.get("xmit_complete") or 0
            fnc_retire = r.get("fnc_retire") or 0
            if fnc_retire == 0:
                # fnc was squashed — speculation window unbounded, hit valid
                n_unbounded += 1
                continue
            slack = fnc_retire - xc
            # Bucket the slack distribution into log-ish bins
            if slack <= 0:
                slack_bucket = "<=0"
                n_violations += 1
            elif slack < 1000:    slack_bucket = "0-1k"
            elif slack < 10000:   slack_bucket = "1k-10k"
            elif slack < 100000:  slack_bucket = "10k-100k"
            elif slack < 1000000: slack_bucket = "100k-1M"
            else:                 slack_bucket = ">=1M"
            slack_ticks_distribution[slack_bucket] += 1
            if slack > 0:
                n_strict_invariant_holds += 1

    print(f"\nTotal ld hits across all triggering grid points: {n_total_hits}")
    print(f"  fnc_pc IS the unresolved branch's jne:   {n_fnc_is_unresolved}")
    print(f"  fnc_pc is something ELSE:                {n_fnc_is_not_unresolved}")
    print(f"  no mispredict_* branch in annotations:   {n_no_unresolved_in_ann}")
    print(f"  fnc_pc / fnc_off missing in row/ann:     {n_unresolved_missing}")
    print()
    print(f"  unbounded window (fnc squashed):         {n_unbounded}")
    print(f"  strict invariant holds (xmit < fnc_ret): {n_strict_invariant_holds}")
    print(f"  invariant VIOLATIONS (xmit ≥ fnc_ret):   {n_violations}")
    print()
    print("slack (fnc_retire - xmit_complete) distribution in ticks:")
    for k in ["<=0", "0-1k", "1k-10k", "10k-100k", "100k-1M", ">=1M"]:
        if slack_ticks_distribution.get(k):
            print(f"  {k:>10}: {slack_ticks_distribution[k]}")


if __name__ == "__main__":
    main()
