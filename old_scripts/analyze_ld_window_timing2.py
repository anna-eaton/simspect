#!/usr/bin/env python3
"""
analyze_ld_window_timing2.py — STT_6 not-taken ld hits: timing window analysis.

Three plots:
  1. Histogram: load completion position within the UNRESOLVED-BRANCH SPECULATION
     WINDOW — fraction of (fnc_retire - fnc_fetch) elapsed when xmit_complete.
     Window = [fnc_fetch .. fnc_retire] (branch predicts → branch resolves).

  2. Histogram: load completion position within the COMMIT WINDOW —
     fraction of (fnc_retire - lc_retire) elapsed when xmit_complete.
     Window = [lc_retire .. fnc_retire] (last-committed retires → fnc retires).

  3. Bar chart: resolved-branch stall length vs number of ld hits, segmented by
     number of resolved branches in the test.

Plots 2 and 3 use existing sweep raw results (no re-run needed).
Plot 1 requires fnc_fetch which is not stored in the original raw results, so
this script re-runs each hitting (stem, grid_idx) pair with check_ld_timing.py
to collect that field.  Results are cached in TIMING_CACHE so subsequent runs
are instant.

Usage:
    python3 analyze_ld_window_timing2.py [--jobs N] [--force]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import subprocess
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT         = Path(__file__).parent
EXP_DIR      = ROOT / "experiments" / "mispredict_not_taken" / "STT_6"
RAW_DIR      = EXP_DIR / "sweep" / "raw_results"
VARIANT_DIR  = EXP_DIR / "sweep" / "variants"
MANIFEST_F   = EXP_DIR / "sweep" / "manifest.json"
ANN_DIR      = EXP_DIR / "ann"
TIMING_CACHE = EXP_DIR / "sweep" / "ld_timing_results.json"
STAGE3       = ROOT / "STAGE3_gem5"
PLOTS_DIR    = ROOT / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

# gem5 env (mirrors run_config_STT_5.jsonc)
GEM5_ENV = {
    **os.environ,
    "SIMSPECT_GEM5_BIN":      "/work/gem5-recon-modded/build/X86/gem5.opt",
    "SIMSPECT_GEM5_DIR":      "/work/gem5-recon-modded",
    "SIMSPECT_SE_CONFIG":     "/work/gem5-recon-modded/configs/example/se.py",
    "SIMSPECT_BRANCH_ANN_ENABLE": "1",
}

MODEL = "STT_6"


# ── Collect existing ld hits ───────────────────────────────────────────────────

def load_existing_hits() -> list[dict]:
    """All (stem, grid_idx, row) for ld hits from existing raw results."""
    hits = []
    for bf in sorted(RAW_DIR.glob("grid*_batch*_check_ld.py.json")):
        m = re.search(r"grid(\d+)_batch", bf.name)
        gi = int(m.group(1)) if m else -1
        rows = json.loads(bf.read_text())
        for r in rows:
            if r.get("issued_in_window"):
                hits.append({**r, "grid_idx": gi})
    return hits


# ── Re-run with check_ld_timing.py (to get fnc_fetch) ────────────────────────

def rerun_for_timing(hits: list[dict], jobs: int) -> dict[tuple, dict]:
    """Re-run each hitting (stem, grid_idx) with check_ld_timing.py.

    Returns {(stem, grid_idx): result_row} with fnc_fetch populated.
    """
    # Group by grid_idx so we can batch per variant dir.
    by_grid: dict[int, list[str]] = defaultdict(list)
    for h in hits:
        by_grid[h["grid_idx"]].append(h["name"])

    results: dict[tuple, dict] = {}

    for gi, stems in sorted(by_grid.items()):
        vdir = VARIANT_DIR / f"point_{gi:04d}"
        if not vdir.exists():
            print(f"  [warn] variant dir missing: {vdir}")
            continue

        print(f"  grid{gi}: re-running {len(stems)} ld hit tests "
              f"(variant dir: {vdir.name})")

        with tempfile.TemporaryDirectory(prefix=f"simspect_timing_g{gi}_") as tmp:
            tmp_path = Path(tmp)
            # Symlink / copy only the hitting stems.
            for stem in stems:
                s_src  = vdir / f"{stem}.s"
                a_src  = vdir / f"{stem}.ann.json"
                if not s_src.exists() or not a_src.exists():
                    print(f"    [warn] missing variant files for {stem}")
                    continue
                # Symlink the .s (already a symlink to asm/)
                dst_s = tmp_path / f"{stem}.s"
                dst_s.symlink_to(s_src.resolve())
                shutil.copy(a_src, tmp_path / f"{stem}.ann.json")

            batch_out = tmp_path / "results.json"
            cmd = [
                sys.executable,
                str(STAGE3 / "check_ld_timing.py"),
                str(tmp_path),
                "--jobs",   str(jobs),
                "--out",    str(batch_out),
                "--scheme", "2",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  env=GEM5_ENV)
            if proc.returncode != 0:
                print(f"  [err] check_ld_timing.py failed for grid{gi}:")
                for line in (proc.stderr or "").splitlines()[-5:]:
                    print(f"    {line}")

            if batch_out.exists():
                batch_rows = json.loads(batch_out.read_text())
                for r in batch_rows:
                    results[(r["name"], gi)] = r
            else:
                print(f"  [warn] no output from grid{gi} run")

    return results


# ── Load annotation info ───────────────────────────────────────────────────────

def load_ann_info(stems: set[str]) -> dict[str, dict]:
    """Load n_resolved and n_unresolved per stem from ann.json."""
    info = {}
    for stem in stems:
        ap = ANN_DIR / f"{stem}.ann.json"
        if not ap.exists():
            info[stem] = {"n_resolved": 0, "n_unresolved": 0}
            continue
        try:
            ann = json.loads(ap.read_text())
            anns = ann.get("annotations", [])
            n_res = sum(1 for a in anns if a.get("mode") == "correctly_not_taken")
            n_unr = sum(1 for a in anns
                        if a.get("mode") in ("mispredict_not_taken",
                                             "mispredict_taken"))
            info[stem] = {"n_resolved": n_res, "n_unresolved": n_unr}
        except Exception:
            info[stem] = {"n_resolved": 0, "n_unresolved": 0}
    return info


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs",  type=int, default=40)
    ap.add_argument("--force", action="store_true",
                    help="Re-run even if timing cache exists")
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # ── Step 1: Load existing ld hits ─────────────────────────────────────────
    print("Loading existing ld hit rows …")
    hits = load_existing_hits()
    print(f"  {len(hits)} hitting (stem, grid_idx) pairs")

    # ── Step 2: Re-run for fnc_fetch (cached) ─────────────────────────────────
    if not args.force and TIMING_CACHE.exists():
        print(f"\nLoading cached timing results from {TIMING_CACHE.name} …")
        timing_raw = json.loads(TIMING_CACHE.read_text())
        timing: dict[tuple, dict] = {
            (r["name"], r["grid_idx"]): r for r in timing_raw
        }
        print(f"  {len(timing)} cached entries")
    else:
        print(f"\nRe-running {len(hits)} ld hit variants with check_ld_timing.py "
              f"(jobs={args.jobs}) …")
        timing = rerun_for_timing(hits, args.jobs)
        print(f"  Got timing for {len(timing)} (stem, grid_idx) pairs")
        # Cache results
        cache_rows = [
            {**row, "grid_idx": gi}
            for (stem, gi), row in timing.items()
        ]
        TIMING_CACHE.write_text(json.dumps(cache_rows, indent=2))
        print(f"  Cached → {TIMING_CACHE}")

    # ── Step 3: Load ann info ─────────────────────────────────────────────────
    all_stems = {h["name"] for h in hits}
    ann_info  = load_ann_info(all_stems)

    # ── Step 4: Assemble per-(stem, grid_idx) rows for plotting ───────────────
    # Merge timing (fnc_fetch) into hit rows.
    combined: list[dict] = []
    n_missing_timing = 0
    for h in hits:
        key = (h["name"], h["grid_idx"])
        t   = timing.get(key)
        if t is None:
            n_missing_timing += 1
            continue
        row = {
            "name":        h["name"],
            "grid_idx":    h["grid_idx"],
            "xmit_complete": h.get("xmit_complete") or t.get("xmit_complete") or 0,
            "lc_retire":     h.get("lc_retire")     or t.get("lc_retire")     or 0,
            "fnc_retire":    h.get("fnc_retire")     or t.get("fnc_retire")     or 0,
            "fnc_fetch":     t.get("fnc_fetch")  or 0,
            "lc_fetch":      t.get("lc_fetch")   or 0,
            "n_resolved":    ann_info.get(h["name"], {}).get("n_resolved", 0),
            "timing_hit":    t.get("issued_in_window", False),
        }
        combined.append(row)

    if n_missing_timing:
        print(f"  [warn] {n_missing_timing} hit rows had no timing entry")
    print(f"  {len(combined)} combined rows for plotting")

    # ── Plot 1: Position in unresolved-branch SPECULATION WINDOW ─────────────
    # window = [fnc_fetch .. fnc_retire]
    print("\n── Plot 1: speculation window position ──")
    spec_positions = []
    for r in combined:
        xc  = r["xmit_complete"]
        ff  = r["fnc_fetch"]
        fr  = r["fnc_retire"]
        if not (xc > 0 and ff > 0 and fr > ff):
            continue
        pos = (xc - ff) / (fr - ff)
        spec_positions.append(pos)
    print(f"  {len(spec_positions)} data points (with valid fnc_fetch)")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(spec_positions, bins=40, color="#4C72B0", edgecolor="white")
    ax.axvline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6,
               label="branch predicts (fnc_fetch)")
    ax.axvline(1, color="gray", linestyle=":",  linewidth=0.8, alpha=0.6,
               label="branch resolves (fnc_retire)")
    ax.set_xlabel(
        "Load completion position in unresolved-branch speculation window\n"
        "(0 = branch predicts, 1 = branch resolves)")
    ax.set_ylabel("# hitting (test, stall-config) pairs")
    ax.set_title(f"{MODEL} not-taken ld hits: load timing in speculation window\n"
                 f"(n={len(spec_positions)})")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    out1 = PLOTS_DIR / f"{MODEL}_nt_ld_speculation_window_position.png"
    fig.savefig(out1, dpi=140)
    plt.close(fig)
    print(f"  wrote {out1}")

    # ── Plot 2: Position in COMMIT WINDOW ─────────────────────────────────────
    # window = [lc_retire .. fnc_retire]
    print("\n── Plot 2: commit window position ──")
    commit_positions = []
    for r in combined:
        xc  = r["xmit_complete"]
        lc  = r["lc_retire"]
        fr  = r["fnc_retire"]
        if not (xc > 0 and fr > 0):
            continue
        # lc_retire=0 means no committed instruction; window is [0, fnc_retire]
        if fr <= lc:
            continue
        pos = (xc - lc) / (fr - lc)
        commit_positions.append(pos)
    print(f"  {len(commit_positions)} data points")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(commit_positions, bins=40, color="#DD8452", edgecolor="white")
    ax.axvline(0, color="gray", linestyle="--", linewidth=0.8, alpha=0.6,
               label="last-committed retires (lc_retire)")
    ax.axvline(1, color="gray", linestyle=":",  linewidth=0.8, alpha=0.6,
               label="branch resolves (fnc_retire)")
    ax.set_xlabel(
        "Load completion position in commit window\n"
        "(0 = lc_retire, 1 = fnc_retire)")
    ax.set_ylabel("# hitting (test, stall-config) pairs")
    ax.set_title(f"{MODEL} not-taken ld hits: load timing in commit window\n"
                 f"(n={len(commit_positions)})")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    out2 = PLOTS_DIR / f"{MODEL}_nt_ld_commit_window_position.png"
    fig.savefig(out2, dpi=140)
    plt.close(fig)
    print(f"  wrote {out2}")

    # ── Plot 3: Resolved-branch stall vs number of ld hits ───────────────────
    # For each hitting (stem, grid_idx) pair, compute max_stall across
    # resolved branches in that grid point, then tally hits by (n_resolved, max_stall).
    print("\n── Plot 3: stall length vs hit count ──")

    # Build stalls per (stem, grid_idx) from the original hit rows.
    # The stall info is in the manifest.
    manifest = json.loads(MANIFEST_F.read_text())
    # manifest[stem] = list of stall_dicts, one per grid_idx
    # Each stall_dict is {branch_pc_str: stall_value}

    seg: dict[tuple, int] = defaultdict(int)   # (n_resolved, max_stall) -> hit_count
    n_no_manifest = 0
    for h in hits:
        stem = h["name"]
        gi   = h["grid_idx"]
        n_res = ann_info.get(stem, {}).get("n_resolved", 0)
        grid = manifest.get(stem, [])
        if gi < len(grid):
            stalls = grid[gi]
            max_stall = max(stalls.values()) if stalls else 0
        else:
            max_stall = 0
            n_no_manifest += 1
        seg[(n_res, int(max_stall))] += 1

    if n_no_manifest:
        print(f"  [warn] {n_no_manifest} hits had no manifest entry")

    # Print table
    print(f"  {'n_resolved':>12} {'max_stall':>10} {'hits':>8}")
    for (nr, ms), cnt in sorted(seg.items()):
        print(f"  {nr:>12} {ms:>10} {cnt:>8}")

    # Group by n_resolved
    n_res_values = sorted({nr for (nr, ms) in seg})
    stall_values = sorted({ms for (nr, ms) in seg})

    # Bar chart: one group per stall value, bars colored by n_resolved
    colors = {0: "#888888", 1: "#4C72B0", 2: "#DD8452", 3: "#55A868", 4: "#C44E52"}
    x      = range(len(stall_values))
    width  = 0.8 / max(len(n_res_values), 1)

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, nr in enumerate(n_res_values):
        ys = [seg.get((nr, ms), 0) for ms in stall_values]
        offset = (i - len(n_res_values) / 2 + 0.5) * width
        bars = ax.bar([xi + offset for xi in x], ys, width=width,
                      label=f"{nr} resolved branch{'es' if nr != 1 else ''}",
                      color=colors.get(nr, "black"), alpha=0.85)
        for bar, y in zip(bars, ys):
            if y > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                        str(y), ha="center", va="bottom", fontsize=7)

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{ms:,}" for ms in stall_values])
    ax.set_xlabel("Max resolved-branch stall applied in grid point (cycles)")
    ax.set_ylabel("# hitting (test, stall-config) pairs")
    ax.set_title(f"{MODEL} not-taken ld hits: resolved-branch stall vs hit count\n"
                 f"(total {sum(seg.values())} hitting grid-point runs, "
                 f"{len(all_stems)} unique stems)")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    out3 = PLOTS_DIR / f"{MODEL}_nt_ld_stall_vs_hits.png"
    fig.savefig(out3, dpi=140)
    plt.close(fig)
    print(f"  wrote {out3}")

    print(f"\nDone.  Plots written to {PLOTS_DIR}/")


if __name__ == "__main__":
    main()
