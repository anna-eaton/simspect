#!/usr/bin/env python3
"""
analyze_ld_timing.py — for STT_6's load (ld) transmitters:

  (1) Plot stall-vs-hit-rate, segmented by resolved-branch count
  (2) Plot histogram of xmit_complete's position within the speculation
      window (normalized to [0,1] between lc_retire and fnc_retire)
  (3) Verify invariant: every triggering load completes BEFORE the
      unresolved branch's broadcast (i.e. xmit_complete < fnc_retire),
      which is what "speculation primitive unresolved at xmit time" means.

Reads raw_results/ batches directly so we have the actual xmit_complete /
fnc_retire ticks (sidecars store only the boolean verdict).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT       = Path(__file__).parent
MODEL      = "STT_6"
ANN_DIR    = ROOT / "generated" / MODEL / "ann"
SWEEP_DIR  = ROOT / "generated" / MODEL / "sweep"
RAW_DIR    = SWEEP_DIR / "raw_results"
PLOTS_DIR  = ROOT / "plots"
PLOTS_DIR.mkdir(exist_ok=True)


def load_raw_results() -> list[dict]:
    """All per-variant rows from every batch file. Each row has:
       name, xmit_complete, lc_retire, fnc_retire, issued_in_window, ..."""
    rows = []
    for bf in sorted(RAW_DIR.glob("grid*_batch*.json")):
        try:
            rows.extend(json.loads(bf.read_text()))
        except Exception as e:
            print(f"  warn: {bf.name}: {e}")
    return rows


def load_manifest() -> dict:
    return json.loads((SWEEP_DIR / "manifest.json").read_text())


def main() -> None:
    print(f"reading raw batch files from {RAW_DIR} …")
    raw = load_raw_results()
    print(f"  {len(raw)} raw variant-run rows")

    # Build {stem -> xmit_kind} from ann.json
    print("loading xmit kinds …")
    xmit_kind = {}
    n_resolved_per_stem = {}
    for ap in ANN_DIR.glob("*.ann.json"):
        try:
            a = json.loads(ap.read_text())
        except Exception:
            continue
        stem = ap.stem.replace(".ann", "")
        xmit_kind[stem] = (a.get("xmit") or {}).get("kind", "?")
        anns = a.get("annotations", [])
        n_resolved_per_stem[stem] = sum(1 for x in anns
                                        if x.get("mode") == "correctly_not_taken")
    print(f"  {len(xmit_kind)} ann.json files; xmit-kind counts: "
          f"{Counter(xmit_kind.values())}")

    # Map manifest to recover (stem, grid_idx) → stalls (we lost this in raw_results)
    manifest = load_manifest()

    # Restrict to ld
    ld_stems = {s for s, k in xmit_kind.items() if k == "ld"}
    print(f"\nld tests: {len(ld_stems)}")

    # For each grid-idx batch file, parse grid_idx from name and match rows
    # to (stem, grid_idx) → stalls
    re_grid = re.compile(r"grid(\d+)_batch")
    grid_idx_of = {}  # batch_file_name → grid_idx
    for bf in RAW_DIR.glob("grid*_batch*.json"):
        m = re_grid.search(bf.name)
        if m:
            grid_idx_of[bf.name] = int(m.group(1))

    # Collect ld-only variant rows with their stall info
    # Each row dict gets augmented with: stem, grid_idx, stalls_dict, sum_stall
    ld_runs = []   # list of dicts
    for bf in sorted(RAW_DIR.glob("grid*_batch*.json")):
        gi = grid_idx_of.get(bf.name)
        if gi is None: continue
        try:
            batch_rows = json.loads(bf.read_text())
        except Exception:
            continue
        for r in batch_rows:
            stem = r.get("name")
            if stem not in ld_stems: continue
            grid = manifest.get(stem, [])
            stalls = grid[gi] if gi < len(grid) else {}
            r2 = dict(r)
            r2["grid_idx"] = gi
            r2["stalls_dict"] = stalls
            r2["n_resolved"] = n_resolved_per_stem.get(stem, 0)
            r2["max_stall"]  = max(stalls.values()) if stalls else 0
            r2["sum_stall"]  = sum(stalls.values()) if stalls else 0
            ld_runs.append(r2)
    print(f"ld variant-runs: {len(ld_runs)}")

    # ── (1) Stall vs hit-rate, segmented by n_resolved ───────────────────────
    # For each (n_resolved, single-branch-stall-value), compute hit rate.
    # Since stalls are a dict {pc:val}, we segment by "stall configuration":
    #   - 0 resolved: only 1 grid point, sum_stall=0
    #   - 1 resolved: stall is a single value (0/500/2500)
    #   - 2 resolved: stall is a pair; we plot by max_stall and sum_stall
    print("\n── (1) ld stall → hit rate ──")
    seg = defaultdict(lambda: [0, 0])  # (n_resolved, max_stall) -> [hits, total]
    for r in ld_runs:
        key = (r["n_resolved"], r["max_stall"])
        seg[key][1] += 1
        if r.get("issued_in_window"):
            seg[key][0] += 1
    by_nresolved = defaultdict(list)
    for (n, ms), (h, t) in seg.items():
        by_nresolved[n].append((ms, h, t))
    for n in sorted(by_nresolved):
        by_nresolved[n].sort()
        print(f"  n_resolved={n}:")
        for ms, h, t in by_nresolved[n]:
            print(f"    max_stall={ms:>5}  {h:>6}/{t:<6} ({100*h/t:>5.2f}%)")

    # Plot
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = {0: "#888888", 1: "#4C72B0", 2: "#DD8452"}
    for n in sorted(by_nresolved):
        xs = [ms for ms, _, _ in by_nresolved[n]]
        ys = [100.0 * h / t for _, h, t in by_nresolved[n]]
        ax.plot(xs, ys, marker="o", linewidth=2, label=f"{n} resolved branch(es)",
                color=colors.get(n, "black"))
        for ms, h, t in by_nresolved[n]:
            ax.text(ms, 100.0 * h / t + 1.0, f"{h}/{t}", ha="center", fontsize=7)
    ax.set_xlabel("stall cycles applied to resolved branches (max in grid pt)")
    ax.set_ylabel("hit rate (%)")
    ax.set_title(f"{MODEL}: ld trigger rate vs resolved-branch stall")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = PLOTS_DIR / f"{MODEL}_ld_stall_vs_hit_rate.png"
    fig.savefig(out, dpi=140); plt.close(fig)
    print(f"  wrote {out}")

    # ── (2) xmit_complete position within window, histogram ──────────────────
    print("\n── (2) xmit timing within [lc_retire, fnc_retire] (ld hits only) ──")
    positions    = []   # normalized (0..1) position of xmit_complete in window
    from_lc      = []   # xmit_complete - lc_retire  (cycles after window opens)
    to_fnc       = []   # fnc_retire - xmit_complete (cycles before window closes)
    window_sizes = []   # fnc_retire - lc_retire
    for r in ld_runs:
        if not r.get("issued_in_window"): continue
        xc  = r.get("xmit_complete") or 0
        lc  = r.get("lc_retire")     or 0
        fnc = r.get("fnc_retire")    or 0
        if not (xc > 0 and fnc > 0 and fnc > lc): continue
        positions.append((xc - lc) / (fnc - lc))
        from_lc.append(xc - lc)
        to_fnc.append(fnc - xc)
        window_sizes.append(fnc - lc)
    print(f"  triggering ld grid-points with valid window: {len(positions)}")
    if window_sizes:
        wc = Counter(window_sizes)
        print(f"  window size (fnc_retire - lc_retire) distribution:")
        for ws in sorted(wc):
            print(f"    {ws} cycles: {wc[ws]}")
        fc = Counter(from_lc)
        print(f"  xmit_complete - lc_retire distribution:")
        for d in sorted(fc):
            print(f"    +{d} cycles: {fc[d]}")

    # normalized position (kept for reference, now redundant if window is tiny)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(positions, bins=40, color="#4C72B0", edgecolor="white")
    ax.set_xlabel("xmit_complete position within window (0 = lc_retire, 1 = fnc_retire)")
    ax.set_ylabel("# triggering grid points")
    ax.set_title(f"{MODEL}: ld xmit-completion timing within speculation window")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    out = PLOTS_DIR / f"{MODEL}_ld_xmit_position_in_window.png"
    fig.savefig(out, dpi=140); plt.close(fig)
    print(f"  wrote {out}")

    # absolute-cycle timing — 3-panel plot
    if from_lc:
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        fl_max  = max(from_lc)
        tf_max  = max(to_fnc)
        ws_max  = max(window_sizes)

        axes[0].hist(from_lc,      bins=range(0, fl_max + 2), color="#4C72B0", edgecolor="white")
        axes[0].set_xlabel("xmit_complete − lc_retire (cycles)")
        axes[0].set_ylabel("# triggering grid points")
        axes[0].set_title("cycles after lc_retire")
        axes[0].xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        axes[0].grid(alpha=0.3, axis="y")

        axes[1].hist(to_fnc,       bins=range(0, tf_max + 2), color="#DD8452", edgecolor="white")
        axes[1].set_xlabel("fnc_retire − xmit_complete (cycles)")
        axes[1].set_ylabel("# triggering grid points")
        axes[1].set_title("cycles before fnc_retire")
        axes[1].xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        axes[1].grid(alpha=0.3, axis="y")

        axes[2].hist(window_sizes, bins=range(1, ws_max + 2), color="#55A868", edgecolor="white")
        axes[2].set_xlabel("fnc_retire − lc_retire (cycles)")
        axes[2].set_ylabel("# triggering grid points")
        axes[2].set_title("speculation window size")
        axes[2].xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        axes[2].grid(alpha=0.3, axis="y")

        fig.suptitle(f"{MODEL}: ld xmit absolute timing (hits only)", fontsize=13)
        fig.tight_layout()
        out2 = PLOTS_DIR / f"{MODEL}_ld_xmit_absolute_timing.png"
        fig.savefig(out2, dpi=140); plt.close(fig)
        print(f"  wrote {out2}")

    # ── (3) Verify invariant: every triggering load completes BEFORE fnc retires ──
    print("\n── (3) verifying invariant: xmit_complete < fnc_retire for all hits ──")
    violations = []
    for r in ld_runs:
        if not r.get("issued_in_window"): continue
        xc  = r.get("xmit_complete") or 0
        fnc = r.get("fnc_retire") or 0
        if not (fnc > 0):  # squashed → infinity (the check_ld treats fnc==0 as ∞)
            continue
        if xc >= fnc:
            violations.append((r["name"], xc, fnc))
    print(f"  {len(violations)} violations (xmit_complete ≥ fnc_retire) "
          f"out of all triggering ld grid points")
    if violations:
        print("  first 10:")
        for v in violations[:10]:
            print(f"    {v[0]}: xmit_complete={v[1]}, fnc_retire={v[2]}")
    else:
        print("  ✓ every triggering ld load completes BEFORE the unresolved "
              "branch resolves — speculation primitive is unresolved at xmit time")

    # Also count how many had fnc_retire==0 (branch was squashed; window upper bound = ∞)
    n_squashed_fnc = sum(1 for r in ld_runs
                        if r.get("issued_in_window") and (r.get("fnc_retire") or 0) == 0)
    print(f"  (note: {n_squashed_fnc} triggering grid points had fnc_retire=0 — "
          f"the fnc inst was itself squashed, so the window is unbounded above)")


if __name__ == "__main__":
    main()
