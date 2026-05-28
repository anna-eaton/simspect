#!/usr/bin/env python3
"""Plot hit category breakdown across model/branch-mode runs."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── Data ─────────────────────────────────────────────────────────────────────
runs = [
    "STT_5",
    "STT_6\nnot-taken",
    "STT_6\ntaken",
    "Recon_6\nnot-taken",
]

data = {
    #            STT_5  STT_6-NT  STT_6-T  Recon_6-NT
    "SLF":       [270,   872,      878,      695],
    "BR":        [0,     309,      281,      246],
    "LL":        [0,     0,        0,        0],
    "OtherLoad": [0,     0,        0,        0],
    "Other":     [591,   0,        0,        0],
}
totals = [861, 1181, 1159, 941]

# ── Style ─────────────────────────────────────────────────────────────────────
colors = {
    "SLF":       "#4e79a7",
    "BR":        "#f28e2b",
    "LL":        "#59a14f",
    "OtherLoad": "#76b7b2",
    "Other":     "#b07aa1",
}

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# ── Left: stacked absolute counts ────────────────────────────────────────────
ax = axes[0]
x = np.arange(len(runs))
bottoms = np.zeros(len(runs))
for cat, counts in data.items():
    vals = np.array(counts, dtype=float)
    bars = ax.bar(x, vals, bottom=bottoms, color=colors[cat], label=cat, width=0.55)
    for i, (v, b) in enumerate(zip(vals, bottoms)):
        if v > 10:
            ax.text(x[i], b + v / 2, str(int(v)),
                    ha="center", va="center", fontsize=9, color="white", fontweight="bold")
    bottoms += vals

ax.set_xticks(x)
ax.set_xticklabels(runs, fontsize=10)
ax.set_ylabel("Hit count")
ax.set_title("Hit categories — absolute count")
ax.legend(loc="upper right", fontsize=9)
ax.set_ylim(0, max(totals) * 1.1)

# ── Right: stacked percentage ─────────────────────────────────────────────────
ax = axes[1]
bottoms = np.zeros(len(runs))
for cat, counts in data.items():
    pcts = np.array([c / t * 100 for c, t in zip(counts, totals)])
    bars = ax.bar(x, pcts, bottom=bottoms, color=colors[cat], label=cat, width=0.55)
    for i, (v, b) in enumerate(zip(pcts, bottoms)):
        if v > 2:
            ax.text(x[i], b + v / 2, f"{v:.0f}%",
                    ha="center", va="center", fontsize=9, color="white", fontweight="bold")
    bottoms += pcts

ax.set_xticks(x)
ax.set_xticklabels(runs, fontsize=10)
ax.set_ylabel("Percentage of hits")
ax.set_title("Hit categories — percentage")
ax.set_ylim(0, 110)
ax.legend(loc="upper right", fontsize=9)

for ax in axes:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

fig.suptitle("Transmitter hit categorization by model / branch mode", fontsize=12, y=1.01)
plt.tight_layout()

out = "/tests/simspect/plots/hit_categories.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved {out}")
