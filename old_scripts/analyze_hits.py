#!/usr/bin/env python3
"""
analyze_hits.py — what kinds of tests trigger the leak window?

For each sweep sidecar `<stem>_sweep.json`, we cross-reference the
corresponding `<stem>.ann.json` to extract test features (xmit kind, branch
counts, etc.) and break down the hit rate by each feature.

Outputs:
  - stdout: a series of cross-tab tables (hit / total / rate%)
  - <model>/plots/hit_rate_by_*.png : one plot per feature dimension
  - <model>/hit_examples.txt : sample hit + non-hit test stems for inspection

Usage:
    python3 analyze_hits.py <model> [<model> ...]
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).parent


def load_test_features(model: str) -> list[dict]:
    """Build a per-test feature record for `model`. One row per test that
    has both a sweep sidecar and an ann.json."""
    sweep_dir = ROOT / "generated" / model / "sweep"
    ann_dir   = ROOT / "generated" / model / "ann"

    sidecar_paths = sorted(sweep_dir.glob("*_sweep.json"))
    print(f"[{model}] loading {len(sidecar_paths)} sidecars + ann.json files")

    rows: list[dict] = []
    for sc_path in sidecar_paths:
        stem = sc_path.stem[:-len("_sweep")] if sc_path.stem.endswith("_sweep") else sc_path.stem
        ann_path = ann_dir / (stem + ".ann.json")
        if not ann_path.exists():
            continue
        try:
            sc  = json.loads(sc_path.read_text())
            ann = json.loads(ann_path.read_text())
        except Exception as e:
            print(f"  skip {stem}: {e}")
            continue

        annotations = ann.get("annotations", [])
        n_resolved   = sum(1 for a in annotations
                           if a.get("mode") == "correctly_not_taken")
        n_unresolved = sum(1 for a in annotations
                           if a.get("mode", "").startswith("mispredict_"))

        xmit = ann.get("xmit") or {}
        cb   = ann.get("commit_boundary") or {}
        lc   = (cb.get("last_committed") or {})
        fnc  = (cb.get("first_noncommitted") or {})

        # xmit position relative to commit boundary
        xmit_pc = xmit.get("pc")
        lc_pc   = lc.get("pc")
        fnc_pc  = fnc.get("pc")
        xmit_dist_from_fnc = (xmit_pc - fnc_pc) if (xmit_pc is not None and
                                                    fnc_pc is not None) else None

        triggered = sc.get("triggered_points", [])
        rows.append(dict(
            stem               = stem,
            xmit_kind          = xmit.get("kind", "?"),
            n_branches         = len(annotations),
            n_resolved         = n_resolved,
            n_unresolved       = n_unresolved,
            xmit_pc            = xmit_pc,
            fnc_pc             = fnc_pc,
            lc_pc              = lc_pc,
            xmit_dist_from_fnc = xmit_dist_from_fnc,
            n_grid_points      = len(sc.get("grid_points", [])),
            n_triggered        = len(triggered),
            triggered          = bool(triggered),
        ))
    return rows


# ── cross-tab helpers ─────────────────────────────────────────────────────────

def crosstab(rows: list[dict], key: str) -> list[tuple]:
    """Return list of (key_value, hits, total, rate%) sorted by key."""
    bucket: dict = defaultdict(lambda: [0, 0])  # value -> [hits, total]
    for r in rows:
        v = r.get(key)
        bucket[v][1] += 1
        if r["triggered"]:
            bucket[v][0] += 1
    out = []
    for v in sorted(bucket, key=lambda x: (x is None, x)):
        h, t = bucket[v]
        out.append((v, h, t, 100.0 * h / t if t else 0.0))
    return out


def print_table(title: str, rows: list[tuple]) -> None:
    print(f"\n{title}")
    print("  " + "─" * 60)
    print(f"  {'value':<24} {'hits':>8} {'total':>8} {'rate%':>8}")
    print("  " + "─" * 60)
    for v, h, t, r in rows:
        print(f"  {str(v):<24} {h:>8} {t:>8} {r:>8.2f}")


def plot_crosstab(title: str, rows: list[tuple],
                  xlabel: str, out_path: Path) -> None:
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [str(r[0]) for r in rows]
    rates  = [r[3] for r in rows]
    totals = [r[2] for r in rows]
    xs = list(range(len(labels)))
    ax.bar(xs, rates, color="#4C72B0", alpha=0.85)
    for x, (_, h, t, r) in zip(xs, rows):
        ax.text(x, r + 0.05, f"{h}/{t}", ha="center", va="bottom",
                fontsize=8)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=0 if len(labels) < 8 else 45,
                       ha="right" if len(labels) >= 8 else "center")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("hit rate (%)")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"  wrote {out_path}")


def write_examples(model: str, rows: list[dict], out_path: Path,
                   k: int = 20) -> None:
    hits     = [r for r in rows if r["triggered"]]
    non_hits = [r for r in rows if not r["triggered"]]
    out_path.write_text("\n".join([
        f"# {model} hit/non-hit examples",
        f"# total: {len(rows)}   hits: {len(hits)}   non-hits: {len(non_hits)}",
        "",
        f"## sample hits (first {k}):",
        *(f"  {r['stem']}  xmit_kind={r['xmit_kind']}  "
          f"branches={r['n_branches']} (resolved={r['n_resolved']}, "
          f"unresolved={r['n_unresolved']})  "
          f"triggered={r['n_triggered']}/{r['n_grid_points']}"
          for r in hits[:k]),
        "",
        f"## sample non-hits (first {k}):",
        *(f"  {r['stem']}  xmit_kind={r['xmit_kind']}  "
          f"branches={r['n_branches']} (resolved={r['n_resolved']}, "
          f"unresolved={r['n_unresolved']})"
          for r in non_hits[:k]),
    ]) + "\n")
    print(f"  wrote {out_path}")


# ── main ──────────────────────────────────────────────────────────────────────

def analyze_one(model: str) -> None:
    rows = load_test_features(model)
    if not rows:
        print(f"[{model}] no test rows — skipping")
        return

    total      = len(rows)
    triggered  = sum(1 for r in rows if r["triggered"])
    print(f"\n=== {model}: {total} tests, {triggered} triggered "
          f"({100.0*triggered/total:.2f}%) ===")

    # Feature breakdowns
    feats = [
        ("xmit kind", "xmit_kind"),
        ("# branches",  "n_branches"),
        ("# resolved branches",   "n_resolved"),
        ("# unresolved branches", "n_unresolved"),
        ("xmit distance from first_noncommitted (PC)", "xmit_dist_from_fnc"),
    ]
    out_dir = ROOT / "generated" / model
    plots_dir = ROOT / "plots"
    plots_dir.mkdir(exist_ok=True)

    for title, key in feats:
        ct = crosstab(rows, key)
        print_table(f"by {title}:", ct)
        safe = key.replace("/", "_")
        plot_crosstab(f"{model}: hit rate by {title}", ct, title,
                      plots_dir / f"{model}_hit_rate_by_{safe}.png")

    # Joint xmit_kind × n_branches
    joint: dict = defaultdict(lambda: [0, 0])
    for r in rows:
        k = (r["xmit_kind"], r["n_branches"])
        joint[k][1] += 1
        if r["triggered"]:
            joint[k][0] += 1
    print("\nby (xmit_kind, # branches):")
    print("  " + "─" * 60)
    print(f"  {'(kind, n_branches)':<24} {'hits':>8} {'total':>8} {'rate%':>8}")
    print("  " + "─" * 60)
    for k in sorted(joint):
        h, t = joint[k]
        print(f"  {str(k):<24} {h:>8} {t:>8} "
              f"{100.0*h/t if t else 0.0:>8.2f}")

    # Examples
    write_examples(model, rows, out_dir / "hit_examples.txt")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python3 analyze_hits.py <model> [<model> ...]")
    for m in sys.argv[1:]:
        analyze_one(m)


if __name__ == "__main__":
    main()
