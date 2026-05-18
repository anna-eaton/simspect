#!/usr/bin/env python3
"""
investigate_br_hits.py — drill into STT_6's br_x leaks.

What we learn:
  1. Which stall configs (per-branch) trigger more often?
  2. Are the triggering tests structurally similar (n_branches, xmit
     position, etc.)?
  3. Pick a canonical example: hit + non-hit pair with same shape, so we
     can diff their pipeviews.

Outputs:
  - generated/STT_6/results_cleaned_br/{window-results.json, window-hits.txt,
        sweep_sidecars/<stem>_sweep.json (one per hit)}
  - stdout: tables summarising the {KIND} hits
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python3 investigate_br_hits.py <model> [<kind>]\n"
                 "  e.g.  STT_6 ld     STT_6 br_x")
    MODEL = sys.argv[1]
    KIND  = sys.argv[2] if len(sys.argv) > 2 else "br_x"

    RESULTS  = ROOT / "generated" / MODEL / "results"  / "window-results.json"
    ANN_DIR  = ROOT / "generated" / MODEL / "ann"
    SWEEP    = ROOT / "generated" / MODEL / "sweep"
    OUT      = ROOT / "generated" / MODEL / f"results_cleaned_{KIND}"
    OUT.mkdir(exist_ok=True)
    OUT_SC   = OUT / "sweep_sidecars"
    OUT_SC.mkdir(exist_ok=True)
    rows = json.loads(RESULTS.read_text())

    # filter: hits AND xmit_kind == br_x
    hits = []
    for r in rows:
        if not r.get("issued_in_window"):
            continue
        stem = r["name"]
        ann_p = ANN_DIR / (stem + ".ann.json")
        if not ann_p.exists():
            continue
        ann = json.loads(ann_p.read_text())
        if (ann.get("xmit") or {}).get("kind") != KIND:
            continue
        hits.append((stem, r, ann))

    print(f"{KIND} hits: {len(hits)}")

    # ── Copy sidecars + write cleaned results ────────────────────────────────
    cleaned = []
    for stem, r, ann in hits:
        rr = dict(r); rr["xmit_kind"] = KIND; cleaned.append(rr)
        src = SWEEP / (stem + "_sweep.json")
        if src.exists():
            shutil.copy(src, OUT_SC / src.name)
    (OUT / "window-results.json").write_text(json.dumps(cleaned, indent=2))
    (OUT / "window-hits.txt").write_text("\n".join(r["name"] for r in cleaned) + "\n")
    print(f"  wrote {OUT}/window-results.json")
    print(f"  copied {len(cleaned)} sidecars → {OUT_SC}")

    # ── Per-feature aggregates ───────────────────────────────────────────────
    # (a) Branch count distribution among hits
    by_branches = Counter(len((sc := json.loads((SWEEP/(stem+"_sweep.json")).read_text())).get("grid_points", [{}])[0].get("stalls") or {})
                          for stem, _, _ in hits)
    print(f"\n{KIND} hits by # branches with stalls (== resolved-branch count):")
    for k in sorted(by_branches): print(f"  {k}: {by_branches[k]}")

    # (b) Which (per-branch-pc, stall) values are common in the triggering set?
    # For each hit, look at `triggered_points` to see which grid points fired
    stall_value_hits = Counter()        # stall_value → triggers
    stall_value_total = Counter()       # stall_value → total occurrences in any grid point of any hit's manifest
    triggered_per_test = Counter()      # n_grid_points_that_triggered → tests
    for stem, _, _ in hits:
        sc = json.loads((SWEEP / (stem + "_sweep.json")).read_text())
        triggered = sc.get("triggered_points", []) or []
        triggered_per_test[len(triggered)] += 1
        for stalls_dict in (sc.get("grid_points") or []):
            stalls = stalls_dict.get("stalls") or {}
            hit_here = bool(stalls_dict.get("issued_in_window"))
            for _pc, v in stalls.items():
                stall_value_total[int(v)] += 1
                if hit_here:
                    stall_value_hits[int(v)] += 1

    print(f"\nstall value frequency in triggering vs total grid points ({KIND} hits only):")
    print(f"  {'stall':>6} {'triggers':>10} {'total':>10} {'rate%':>8}")
    for v in sorted(stall_value_total):
        h = stall_value_hits[v]; t = stall_value_total[v]
        print(f"  {v:>6} {h:>10} {t:>10} {100.0*h/t if t else 0.0:>8.2f}")

    print(f"\n{KIND} hits — triggered grid-points per test:")
    for k in sorted(triggered_per_test): print(f"  {k}: {triggered_per_test[k]} tests")

    # (c) xmit distance from fnc
    by_dist = Counter()
    for stem, _, ann in hits:
        xmit_pc = (ann.get("xmit") or {}).get("pc")
        fnc_pc  = ((ann.get("commit_boundary") or {}).get("first_noncommitted") or {}).get("pc")
        if xmit_pc is not None and fnc_pc is not None:
            by_dist[xmit_pc - fnc_pc] += 1
    print(f"\n{KIND} hits by (xmit_pc - fnc_pc):")
    for k in sorted(by_dist): print(f"  {k}: {by_dist[k]}")

    # ── Pick a canonical example: the smallest test that hits ────────────────
    # Smallest = fewest grid points, since fewer branches = easier to reason about.
    hits_with_size = []
    for stem, r, ann in hits:
        sc = json.loads((SWEEP / (stem + "_sweep.json")).read_text())
        ngp = len(sc.get("grid_points", []))
        n_triggered = len(sc.get("triggered_points", []))
        hits_with_size.append((ngp, n_triggered, stem, ann))
    hits_with_size.sort()

    print(f"\n=== smallest 5 {KIND} hits (n_grid_pts, n_triggered, stem) ===")
    for ngp, nt, stem, ann in hits_with_size[:5]:
        xmit_pc = (ann.get("xmit") or {}).get("pc")
        fnc_pc  = ((ann.get("commit_boundary") or {}).get("first_noncommitted") or {}).get("pc")
        anns    = ann.get("annotations", [])
        n_branches = len(anns)
        n_resolved = sum(1 for a in anns if a.get("mode") == "correctly_not_taken")
        print(f"  {stem}  grid={ngp}  triggered={nt}  "
              f"n_branches={n_branches}({n_resolved} resolved)  "
              f"xmit_pc={xmit_pc}  fnc_pc={fnc_pc}")


if __name__ == "__main__":
    main()
