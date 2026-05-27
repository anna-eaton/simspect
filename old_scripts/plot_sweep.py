#!/usr/bin/env python3
"""
plot_sweep.py — visualize gem5-sweep hit distributions.

Reads all `<stem>_sweep.json` sidecars under generated/<model>/sweep/ and
produces three plots:

  1. Hit-rate bar chart per individual stall value, marginalised across
     branches (i.e. "for each occurrence of stall=N in any grid point,
     how often did that grid point trigger?").
  2. Histogram of "number of branches per test" — gives a feel for how
     much grid blow-up affects the corpus.
  3. Per-test trigger count distribution (how many grid points triggered
     per triggering test).

Output: PNG files in <model>/plots/. No X11 required (Agg backend).

Usage:
    python3 plot_sweep.py <model>        # e.g. STT_5
    python3 plot_sweep.py STT_5 STT_6    # multiple models, side-by-side
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless — no X11 needed
import matplotlib.pyplot as plt


def load_sidecars(model: str) -> list[dict]:
    base = Path(__file__).parent / "generated" / model / "sweep"
    files = list(base.glob("*_sweep.json"))
    print(f"[{model}] loading {len(files)} sweep sidecars from {base}")
    out = []
    for p in files:
        try:
            out.append(json.loads(p.read_text()))
        except Exception as e:
            print(f"  warn: {p.name}: {e}")
    return out


def stat_hit_rate_per_stall(sidecars: list[dict]) -> dict[int, tuple[int, int]]:
    """Return {stall_value: (triggers, total)} across all (branch, gridpoint)
    occurrences in the corpus."""
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # [hit, total]
    for sc in sidecars:
        for gp in sc.get("grid_points", []):
            hit = bool(gp.get("issued_in_window"))
            for _pc, stall in (gp.get("stalls") or {}).items():
                counts[int(stall)][1] += 1
                if hit:
                    counts[int(stall)][0] += 1
    return {k: tuple(v) for k, v in counts.items()}


def stat_branches_per_test(sidecars: list[dict]) -> Counter:
    c = Counter()
    for sc in sidecars:
        gps = sc.get("grid_points", [])
        n_branches = len((gps[0].get("stalls") or {})) if gps else 0
        c[n_branches] += 1
    return c


def stat_triggers_per_test(sidecars: list[dict]) -> Counter:
    c = Counter()
    for sc in sidecars:
        n = len(sc.get("triggered_points", []))
        c[n] += 1
    return c


def plot_hit_rate_per_stall(per_model: dict[str, dict],
                            out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    models = list(per_model.keys())
    all_stalls = sorted({s for d in per_model.values() for s in d})
    width = 0.8 / len(models)
    for i, m in enumerate(models):
        d = per_model[m]
        x = [s for s in all_stalls]
        y = [
            (d[s][0] / d[s][1]) if (s in d and d[s][1]) else 0.0
            for s in all_stalls
        ]
        offsets = [xi + (i - (len(models) - 1) / 2) * width for xi in range(len(all_stalls))]
        ax.bar(offsets, y, width=width, label=m)
        # totals as annotations
        for xi, s in enumerate(all_stalls):
            hit, tot = d.get(s, (0, 0))
            if tot:
                ax.text(xi + (i - (len(models) - 1) / 2) * width, 0,
                        f"{hit}/{tot}", ha="center", va="bottom",
                        fontsize=7, rotation=90)
    ax.set_xticks(range(len(all_stalls)))
    ax.set_xticklabels([str(s) for s in all_stalls])
    ax.set_xlabel("stall cycles (resolved branch)")
    ax.set_ylabel("hit rate (issued_in_window / total grid-point occurrences)")
    ax.set_title("Hit rate per stall value, marginalised across branches")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    print(f"  wrote {out_path}")


def plot_branches_per_test(per_model: dict[str, Counter],
                           out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    models = list(per_model.keys())
    all_k = sorted({k for c in per_model.values() for k in c})
    width = 0.8 / len(models)
    for i, m in enumerate(models):
        c = per_model[m]
        offsets = [k + (i - (len(models) - 1) / 2) * width for k in range(len(all_k))]
        ax.bar(offsets, [c.get(k, 0) for k in all_k], width=width, label=m)
    ax.set_xticks(range(len(all_k)))
    ax.set_xticklabels([str(k) for k in all_k])
    ax.set_xlabel("# resolved branches per test")
    ax.set_ylabel("# tests")
    ax.set_title("Resolved-branch count distribution")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    print(f"  wrote {out_path}")


def plot_triggers_per_test(per_model: dict[str, Counter],
                           out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    models = list(per_model.keys())
    all_k = sorted({k for c in per_model.values() for k in c if k > 0})
    if not all_k:
        print(f"  skipping {out_path.name}: no triggering tests")
        return
    width = 0.8 / len(models)
    for i, m in enumerate(models):
        c = per_model[m]
        offsets = [k + (i - (len(models) - 1) / 2) * width for k in range(len(all_k))]
        ax.bar(offsets, [c.get(k, 0) for k in all_k], width=width, label=m)
    ax.set_xticks(range(len(all_k)))
    ax.set_xticklabels([str(k) for k in all_k])
    ax.set_xlabel("# grid points that triggered per (triggering) test")
    ax.set_ylabel("# tests")
    ax.set_title("Per-test trigger-count distribution (only triggering tests)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    print(f"  wrote {out_path}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python3 plot_sweep.py <model> [<model> ...]")
    models = sys.argv[1:]

    rate_per_model: dict[str, dict] = {}
    branches_per_model: dict[str, Counter] = {}
    triggers_per_model: dict[str, Counter] = {}
    summaries: list[str] = []

    for m in models:
        sidecars = load_sidecars(m)
        if not sidecars:
            print(f"  [{m}] no sidecars — skipping")
            continue
        rate_per_model[m]     = stat_hit_rate_per_stall(sidecars)
        branches_per_model[m] = stat_branches_per_test(sidecars)
        triggers_per_model[m] = stat_triggers_per_test(sidecars)

        # text summary
        total = len(sidecars)
        triggered = sum(c for k, c in triggers_per_model[m].items() if k > 0)
        summaries.append(
            f"  {m}: {total} tests, {triggered} triggered "
            f"({100.0*triggered/total:.2f}% hit rate)"
        )

    out_dir = Path(__file__).parent / "plots"
    out_dir.mkdir(exist_ok=True)
    print("\n=== summary ===")
    for s in summaries:
        print(s)
    print("\n=== plots ===")
    plot_hit_rate_per_stall(rate_per_model, out_dir / "hit_rate_per_stall.png")
    plot_branches_per_test(branches_per_model, out_dir / "branches_per_test.png")
    plot_triggers_per_test(triggers_per_model, out_dir / "triggers_per_test.png")
    print(f"\nview: scp them off, or `code {out_dir}/*.png` in VSCode Remote.")


if __name__ == "__main__":
    main()
