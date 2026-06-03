#!/usr/bin/env python3
"""
make_graphs.py — per-(testset x implementation) hit-attribution charts for the SimSpect bug catalog.

For every campaign we actually ran, a SimSpect "hit" (gem5 permits what the Alloy model forbids) is
attributed to the LAYER it really came from — TARGET (real defense bug, the signal), CHECKER (Stage-3
measurement artifact), ALLOY (model over-approx / concretization / enumeration), or PIPELINE/CONFIG.
Bars are grouped and COLORED BY CATEGORY so you can see, per run, whether the discrepancies are real
target bugs or our own model/checker/codegen lying.

All numbers are VERIFIED from disk (results/<run>/diagnostics/buckets/, window-results.json) or from the
durable claudelog.md, with provenance noted inline. Regenerate:  python3 bug/graphs/make_graphs.py
Cross-ref: bug/BUG_TAXONOMY.md (the A*/B*/C*/D* ids), bug/BUGS.md.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

OUT = os.path.dirname(os.path.abspath(__file__))

# ---- category -> color (consistent across every chart) ----------------------------------
CAT = {
    "target":     ("#d62728", "TARGET — real defense bug (the signal)"),
    "target_open":("#d62728", "TARGET candidate — attribution OPEN"),   # drawn hatched
    "checker":    ("#ff7f0e", "CHECKER — Stage-3 measurement artifact"),
    "alloy":      ("#1f77b4", "ALLOY — model over-approx / concretization / enumeration"),
    "pipeline":   ("#d4a017", "PIPELINE — codegen / harness artifact"),
    "config":     ("#7f7f7f", "CONFIG — build/config (not a bug)"),
    "clean":      ("#2ca02c", "no leak — defense holds (0 hits)"),
    "open":       ("#9e9e9e", "UNATTRIBUTED — pre-fix / un-typed run"),
}
def color(c): return CAT[c][0]

# ---- the runs: (testset, implementation/regime, [ (bucket_label, count, category) ], note) ----
# Provenance is in the comment above each block.
RUNS = []

# Recon_6 x Recon(STT+allow_leaked), stock sweep.
# results/Recon_6__20260602_122016 — diagnostics/leak_complete_before_squash.json: 184 ld hits,
# leak=True 1 (inst-014912 = SLF/A2), leak=False 183 (check_ld FP/B1; incl. 3 "OTB" classifier
# false-matches B4). br_x 0. (claudelog 19:22/20:40/23:05)
RUNS.append(("Recon_6", "Recon  (gem5-recon-modded, STT sch2 + allow_leaked)", [
    ("check_ld FP\n(delay_unit bounce, B1)", 183, "checker"),
    ("SLF taint bypass\n(A2, inst-014912)",    1, "target"),
], "184 ld hits -> 1 REAL leak (SLF) + 183 checker FP.  br_x: 0."))

# SPT_6_oneLP x SPT-Fence, stock.
# buckets on disk: constaddr 2961+3079=6040, rf_clobber 28+28=56, NEW 5+17=22.
# claudelog 09:00/22:40 split NEW 22 -> 15 safe-load over-approx (alloy) + 7 STLF check_ld FP (checker).
RUNS.append(("SPT_6_oneLP", "SPT-Fence  (gem5-spt, SpectreSafeFence DDIFT)  [stock]", [
    ("const-addr over-approx\n(C2)",           6040, "alloy"),
    ("rf last-writer clobber\n(C1)",             56, "alloy"),
    ("safe-load over-approx\n(C2, pre-branch)",  15, "alloy"),
    ("STLF check_ld FP\n(B1)",                    7, "checker"),
], "6118 ld hits -> 0 real leaks (all alloy over-approx + checker FP).  br_x: 0."))

# SPT_6_oneLP x SPT-Fence, SLOW-COMM (commitToIEWDelay=4).
# results/experiments/spt_slowcomm_fence__20260602_121858 buckets:
# constaddr 20859+17867=38726, rf_clobber 1933+3029=4962, NEW 1594+2938=4532, postmispred 383+600=983.
# 983 postmispred_producer = the VP<->squash race candidate (A5, same class as STT A4), attribution OPEN.
RUNS.append(("SPT_6_oneLP", "SPT-Fence  (gem5-spt)  [SLOW-COMM, commitToIEWDelay=4]", [
    ("const-addr over-approx\n(C2)",            38726, "alloy"),
    ("rf last-writer clobber\n(C1)",             4962, "alloy"),
    ("pre-branch over-approx\n(C2 residual)",    4532, "alloy"),
    ("post-mispredict producer\nVP-squash race (A5)", 983, "target_open"),
], "49,203 ld hits -> 983 VP-squash-race candidates (open); rest alloy over-approx."))

# STT_6 x STT (/work/stt) stock. results/STT_6_sttbuild__20260602_013615 — ld 11,652 / br_x 4,348 per
# mode, ALL ok, 0 leaks (results.md). Structural notes: dup-PC drop (D1) at gen, stale testset (C4).
RUNS.append(("STT_6", "STT  (work/stt, cwfletcher upstream)  [stock]", [],
    "0 hits — STT defense holds (ld 11,652 + br_x 4,348/mode, all ok).\n"
    "Caveats: testset is pre-RS stale (C4); ~6% br_x dropped at gen by dup-PC (D1)."))

# STT_6_interleave x STT (/work/stt) stock. 0 leaks + 348 'error' rows = sweep-incompleteness (D5).
RUNS.append(("STT_6_interleave", "STT  (work/stt)  [stock]", [
    ("sweep-incomplete\nerror rows (D5)", 348, "pipeline"),
], "0 leaks — STT defense holds.  348 'error' rows = grid-pt-2 batch never written (harness, not a leak)."))

# STT_6 x Recon (recon-modded) stock, PARTIAL (10,163/100k ld swept).
# results/STT_6__20260602_015852 — ld 253 hits (all load->load check_ld FP/B1), br_x 0. (claudelog reconbugs)
RUNS.append(("STT_6", "Recon  (gem5-recon-modded)  [stock, PARTIAL 10k/100k]", [
    ("check_ld FP\n(load->load delay_unit, B1)", 253, "checker"),
], "253 ld hits (partial sweep) -> all check_ld false positives.  br_x: 0.  No store-shaped tests reached yet."))

# STT_6_interleave x Recon, PARTIAL (7,984 ld). 49 hits all checker FP.
RUNS.append(("STT_6_interleave", "Recon  (gem5-recon-modded)  [stock, PARTIAL 8k/100k]", [
    ("check_ld FP\n(load->load, B1)", 49, "checker"),
], "49 ld hits (partial) -> all check_ld false positives."))

# STT_6 x STT (/work/stt) SLOW-COMM, 600/mode SAMPLE (not full corpus).
# results/experiments/slow_comm_squash1 — not_taken 187 hits: 186 VP-squash race (A4, target) + 1 check_ld FP.
RUNS.append(("STT_6", "STT  (work/stt)  [SLOW-COMM, 600-test SAMPLE]", [
    ("VP<->squash race\n(A4, real)", 186, "target"),
    ("check_ld FP (B1)",               1, "checker"),
], "187 not_taken hits (600-sample) -> 186 real VP-squash-race + 1 checker FP.\n"
   "Driver = commitToIEWDelay>=3; 0 hits at stock timing."))

# STT_all x Amulet (STT_AE) — OPEN. results/STT_all_amulet (watcher from 2026-05-28, PRE-B2 fix,
# un-typed _sweep_watcher layout): 9,215 not_taken hits but kind unknown + pre-branch-fix => cannot
# attribute (mix of check_br FP/B2 and possible A3 real branch leaks). AUDIT #1 earlier saw an all-error
# state (caches:true port bug, D4); AUDIT #20 flags the taken-mode asymmetry as unverified.
RUNS.append(("STT_all", "Amulet STT_AE  (work/amulet)  [PRE-FIX, un-typed]", [
    ("unattributed hits\n(pre-B2 fix, un-typed)", 9215, "open"),
], "9,215 hits but NOT attributable: pre-check_br-fix (B2) + un-typed.  Earlier all-error state = D4.\n"
   "Re-run with fixed checkers + kind split before trusting (AUDIT #20)."))


# ---------------------------------------------------------------------------------------
def draw_panel(ax, run):
    testset, impl, buckets, note = run
    title = f"{testset}\n{impl}"
    if not buckets:  # 0-hit / defense-holds panel
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.text(0.5, 0.62, "0 hits", ha="center", va="center",
                fontsize=22, fontweight="bold", color=color("clean"))
        ax.text(0.5, 0.40, "defense holds", ha="center", va="center",
                fontsize=12, color=color("clean"))
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values(): s.set_edgecolor(color("clean")); s.set_linewidth(2)
    else:
        labels  = [b[0] for b in buckets]
        counts  = [b[1] for b in buckets]
        cats    = [b[2] for b in buckets]
        ypos = range(len(buckets))
        bars = ax.barh(list(ypos), counts,
                       color=[color(c) for c in cats], edgecolor="black", linewidth=0.6)
        for bar, c in zip(bars, cats):
            if c == "target_open":            # candidate => hatched
                bar.set_hatch("////"); bar.set_edgecolor("black")
        ax.set_yticks(list(ypos)); ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()
        ax.set_xscale("log")
        ax.set_xlim(0.6, max(counts) * 3)
        for bar, n in zip(bars, counts):
            ax.text(bar.get_width() * 1.15, bar.get_y() + bar.get_height() / 2,
                    f"{n:,}", va="center", ha="left", fontsize=8, fontweight="bold")
        ax.set_xlabel("hit records  (log scale)", fontsize=8)
        ax.tick_params(axis="x", labelsize=7)
    ax.set_title(title, fontsize=9.5, fontweight="bold", pad=6)
    ax.text(0.0, -0.30, note, transform=ax.transAxes, fontsize=7.2, va="top", color="#333333")


def fig_attribution():
    n = len(RUNS); cols = 3; rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(17, 4.4 * rows))
    axes = axes.flatten()
    for ax, run in zip(axes, RUNS):
        draw_panel(ax, run)
    for ax in axes[n:]:
        ax.axis("off")
    legend = [Patch(facecolor=color(k), edgecolor="black", label=CAT[k][1])
              for k in ("target", "target_open", "checker", "alloy", "pipeline", "config", "clean", "open")]
    fig.legend(handles=legend, loc="lower center", ncol=4, fontsize=9, frameon=True,
               bbox_to_anchor=(0.5, -0.005))
    fig.suptitle("SimSpect hit attribution — each testset × implementation, bugs grouped & colored by category\n"
                 "(a 'hit' = gem5 permits what the Alloy model forbids; the question is WHICH LAYER it came from)",
                 fontsize=13, fontweight="bold", y=0.998)
    fig.tight_layout(rect=[0, 0.045, 1, 0.97])
    p = os.path.join(OUT, "hit_attribution_by_category.png")
    fig.savefig(p, dpi=140, bbox_inches="tight"); plt.close(fig)
    return p


def fig_findings_by_category():
    """Catalogued findings (A*/B*/C*/D*) counted by category — regime-independent summary."""
    data = [
        ("TARGET",          5, "target", "A1 OTB · A2 SLF · A3 implicit-channel · A4 STT race · A5 SPT race"),
        ("CHECKER",         4, "checker", "B1 check_ld · B2 check_br · B3 cache-reach · B4 OTB classifier"),
        ("ALLOY",           4, "alloy",   "C1 rf clobber · C2 const-addr · C3 OTB gen-gap · C4 stale-RS testset"),
        ("PIPELINE/CONFIG", 7, "pipeline","D1 dup-PC · D2 pipeview · D3 idivq · D4 amulet caches · D5 sweep · D6 minor · D7 open"),
        ("gem5 generic",    1, "config",  "A6 commitToIEWDelay>=5 livelock (out of scope)"),
    ]
    fig, ax = plt.subplots(figsize=(11, 5.6))
    labels = [d[0] for d in data]; vals = [d[1] for d in data]; cats = [d[2] for d in data]
    bars = ax.bar(labels, vals, color=[color(c) for c in cats], edgecolor="black")
    for bar, d in zip(bars, data):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.08, str(d[1]),
                ha="center", fontsize=12, fontweight="bold")
    ax.set_ylabel("# catalogued findings", fontsize=10)
    ax.set_ylim(0, max(vals) + 1)
    ax.set_title("SimSpect catalogued findings by layer  (see bug/BUG_TAXONOMY.md)",
                 fontsize=12, fontweight="bold")
    ax.tick_params(axis="x", labelsize=10)
    # id list per category, as a footer block (no overlap with bars)
    footer = "\n".join(f"{d[0]:>16s}:  {d[3]}" for d in data)
    fig.text(0.5, 0.015, footer, ha="center", va="bottom", fontsize=7.4,
             family="monospace", color="#333333")
    fig.tight_layout(rect=[0, 0.20, 1, 1])
    p = os.path.join(OUT, "findings_by_category.png")
    fig.savefig(p, dpi=140, bbox_inches="tight"); plt.close(fig)
    return p


def fig_coverage():
    """testset x implementation coverage grid: what was run, and whether hits are cleanly attributed."""
    testsets = ["STT_6", "STT_6_interleave", "Recon_6", "SPT_6_oneLP", "STT_all"]
    impls    = ["STT (work/stt)", "STT slow-comm", "Recon (modded)", "SPT-Fence", "SPT-Fence slow-comm", "Amulet"]
    # cell -> ("status", label)
    grid = {
        ("STT_6","STT (work/stt)"):            ("clean","0 hits"),
        ("STT_6","STT slow-comm"):             ("target","186 race (sample)"),
        ("STT_6","Recon (modded)"):            ("checker","253 FP (partial)"),
        ("STT_6_interleave","STT (work/stt)"): ("clean","0 hits +348 err"),
        ("STT_6_interleave","Recon (modded)"): ("checker","49 FP (partial)"),
        ("Recon_6","Recon (modded)"):          ("target","1 real +183 FP"),
        ("SPT_6_oneLP","SPT-Fence"):           ("alloy","6118 over-approx"),
        ("SPT_6_oneLP","SPT-Fence slow-comm"): ("target_open","983 race +48k aprx"),
        ("STT_all","Amulet"):                  ("open","9215 unattrib."),
    }
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.set_xlim(0, len(impls)); ax.set_ylim(0, len(testsets))
    for (ts, im), (st, lab) in grid.items():
        x = impls.index(im); y = len(testsets) - 1 - testsets.index(ts)
        ax.add_patch(plt.Rectangle((x, y), 1, 1, facecolor=color(st), edgecolor="white",
                                   linewidth=2, alpha=0.92))
        hatch = "////" if st == "target_open" else None
        if hatch:
            ax.add_patch(plt.Rectangle((x, y), 1, 1, facecolor="none", edgecolor="black",
                                       linewidth=0, hatch=hatch))
        tc = "white" if st in ("target","target_open","alloy","config") else "black"
        ax.text(x + 0.5, y + 0.5, lab, ha="center", va="center", fontsize=8,
                color=tc, fontweight="bold")
    ax.set_xticks([i + 0.5 for i in range(len(impls))]); ax.set_xticklabels(impls, fontsize=9, rotation=15, ha="right")
    ax.set_yticks([i + 0.5 for i in range(len(testsets))]); ax.set_yticklabels(list(reversed(testsets)), fontsize=9)
    ax.set_xticks(range(len(impls)+1), minor=True); ax.set_yticks(range(len(testsets)+1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2); ax.tick_params(length=0)
    for s in ax.spines.values(): s.set_visible(False)
    legend = [Patch(facecolor=color(k), edgecolor="black", label=CAT[k][1])
              for k in ("clean","target","target_open","checker","alloy","open")]
    ax.legend(handles=legend, loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8, frameon=True)
    ax.set_title("Coverage: testset × implementation — dominant hit category per run\n"
                 "(blank = not run / not usable)", fontsize=12, fontweight="bold")
    fig.tight_layout()
    p = os.path.join(OUT, "coverage_matrix.png")
    fig.savefig(p, dpi=140, bbox_inches="tight"); plt.close(fig)
    return p


if __name__ == "__main__":
    for f in (fig_attribution(), fig_findings_by_category(), fig_coverage()):
        print("wrote", f)
