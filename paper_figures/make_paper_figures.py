#!/usr/bin/env python3
"""
make_paper_figures.py  —  candidate figures for the SimSpect results writeup.

For each "figure slot" in PAPER_RESULTS.md we emit THREE candidate renderings
(a/b/c) so Anna can pick the one that presents the data best.  Every number is
BAKED IN with a provenance comment pointing at the file on disk / claudelog entry
it came from (same discipline as bug/graphs/make_graphs.py).  Regenerate:

    python3 paper_figures/make_paper_figures.py

Slots:
  F1  what SimSpect found per (testset x defense), attributed by LAYER
  F2  SimSpect vs AMuLeT — scope (per-bug in/out of SimSpect's leakage model)
  F3  test targeting / diversity vs AMuLeT (only 17% of their tests can even leak)
  F4  stall-knob sensitivity (s_U masks, s_R flat, fnc plateau) @ commitToIEWDelay=3
  F5  fragility threshold — leak count vs commitToIEWDelay (the timing-agnosticism test)
  F6  the VP<->squash race mechanism (timeline schematic; STT==SPT shared bad logic)
  F7  the two recon bugs (OTB getOldestTaint + STL/SLF) — gadget schematics
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, FancyBboxPatch, FancyArrowPatch

OUT = os.path.dirname(os.path.abspath(__file__))
def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=140, bbox_inches="tight"); plt.close(fig); print("wrote", p)

# consistent layer colors (match bug/graphs/make_graphs.py + BUG_TAXONOMY.md)
C_TARGET   = "#d62728"   # real defense bug — the signal
C_OPEN     = "#e377c2"   # target candidate, attribution open
C_CHECKER  = "#ff7f0e"   # checker measurement artifact
C_ALLOY    = "#1f77b4"   # alloy over-approx / concretization / enumeration
C_PIPE     = "#d4a017"   # pipeline / codegen
C_CONFIG   = "#7f7f7f"   # config / generic gem5
C_CLEAN    = "#2ca02c"   # defense holds (0 hits)
C_AMULET   = "#8c564b"   # amulet-only / out of scope

# =====================================================================================
# DATA  (all verified from disk on 2026-06-03; provenance in comments)
# =====================================================================================

# --- F1: per-run hit attribution -----------------------------------------------------
# Recon_6__20260602_122016/diagnostics/buckets/summary.json:
#   {check_ld_no_completion:183, recon_slf:1, NEW:0}     (184 ld hits, br_x 0)
# slow_comm_squash1/sample/summary.json (600/mode):
#   not_taken 187 = 186 real race + 1 FP ; taken 44 = 42 real + 2 FP
# slow_comm_squash1/sample_stock/summary.json (600/mode): 0 / 0
# stt_slowcomm_full__.../diagnostics/buckets/summary.json:
#   {stt_vp_squash_race:19845, check_ld_not_real_access:21, NEW:4122}
# results.md: STT_6 sttbuild stock = 0 leaks (11,652 ld + 4,348 br_x / mode)
# SPT_6_oneLP_fence stock: 6118 ld = 6040 constaddr + 56 rf + 15 safe-load + 7 STLF (0 real)
# spt_slowcomm_fence__.../buckets/summary.json:
#   {constaddr_load:67297, rf_clobber:5503, nonspec_cotransmit:358, NEW:4397}
#   claudelog: ~983 of NEW are the post-mispredict Spectre-v1 shape = A5 VP-squash candidates
RUNS = [
    # (label, [(bucket, count, color)], real_count, note)
    ("Recon_6 x Recon-STT\n(scheme2 + allow_leaked, stock)",
        [("check_ld FP (B1)", 183, C_CHECKER), ("SLF bypass (A2) REAL", 1, C_TARGET)],
        1, "1 REAL leak (SLF, inst-014912) + 183 checker FP"),
    ("STT_6 x STT\n(/work/stt, STOCK)",
        [], 0, "0 hits — STT defense holds (11,652 ld + 4,348 br_x/mode)"),
    ("STT_6 x STT\n(/work/stt, SLOW-COMM full corpus)",
        [("check_ld FP (B1)", 21, C_CHECKER), ("VP-squash race (A4) REAL", 19845, C_TARGET),
         ("NEW (un-rerun)", 4122, C_OPEN)],
        19845, "19,845 real VP-squash-race; 0 at stock timing"),
    ("SPT_6_oneLP x SPT-Fence\n(gem5-spt, STOCK)",
        [("const-addr (C2)", 6040, C_ALLOY), ("rf-clobber (C1)", 56, C_ALLOY),
         ("safe-load (C2)", 15, C_ALLOY), ("STLF FP (B1)", 7, C_CHECKER)],
        0, "6,118 ld hits -> 0 real (all model/checker artifact)"),
    ("SPT_6_oneLP x SPT-Fence\n(gem5-spt, SLOW-COMM)",
        [("const-addr (C2)", 67297, C_ALLOY), ("rf-clobber (C1)", 5503, C_ALLOY),
         ("nonspec co-xmit", 358, C_ALLOY), ("NEW (=VP race A5, ~983)", 4397, C_OPEN)],
        0, "VP-squash race shared w/ STT (A5, attribution open); no independent SPT bug"),
]

# --- F2: AMuLeT bug scope (docs/AMULET_VS_SIMSPECT_SCOPE.md per-bug table) ------------
AMULET_BUGS = [
    # (id, defense, channel, in_scope(bool), simspect_finds(str))
    ("UV1", "InvisiSpec", "spec-load L1D eviction",     False, "OUT - Ruby eviction, not a transmitter access"),
    ("UV2", "InvisiSpec", "MSHR contention (timing)",   False, "OUT - shared MSHR, needs input-diff"),
    ("KV1", "InvisiSpec", "L1I spec fetch",             False, "OUT - I-cache state"),
    ("UV3", "CleanupSpec","post-squash L1D residue",    False, "OUT - install is by-design; final-state diff"),
    ("UV4", "CleanupSpec","split-req residue",          False, "OUT - final-state diff"),
    ("UV5", "CleanupSpec","over-cleaning evicts NSL",   False, "OUT - final-state diff"),
    ("KV3", "STT",        "tainted spec STORE -> D-TLB",False, "OUT - store xmit + TLB (not in leakage_function)"),
    ("UV6", "SpecLFB",    "first spec LOAD installs line",True, "IN  - DEMONSTRATED: unsafe first load accesses cache in-window (68/300); secret-recovery PoC pends stimulus"),
]

# --- F3: test targeting (AMuLeT static gadget analysis vs SimSpect by-construction) ---
# /work/amulet-repo/stt_corpus_gadgets.json summary (n=500, all filters):
AMULET_N      = 500
AMULET_LL     = 70    # 14.0%
AMULET_BRX    = 25    # 5.0%
AMULET_EITHER = 85    # 17.0%  (415/500 cannot leak by construction)
AMULET_LL_LOOSE, AMULET_BRX_LOOSE, AMULET_EITHER_LOOSE = 333, 162, 349   # structure-only
SIMSPECT_N    = 100000   # config alloy.max_instances; tag_xm => 100% transmitter-in-protset

# --- F4: stall-knob sensitivity (paper_stalls, STT @ commitToIEWDelay=3, 200/mode) ---
# real_cache_hits (not_taken), 100% bucket-confirmed stt_vp_squash_race (no FP/over-approx):
SU_X = [0, 50, 250, 1000, 5000]; SU_Y = [27, 0, 0, 0, 0]           # stt_sU_*/summary.json
SR_X = [0, 8, 64];               SR_Y = [27, 22, 22]               # stt_sR_*/summary.json
FNC_X = [0, 150, 300];           FNC_Y = [16, 27, 27]              # stt_fnc_*/summary.json

# --- F5: fragility threshold (paper_fragility, bare, real_cache_hits, 300/150 sample) -
FRAG_D = [1, 2, 3, 4]
STT_NT  = [0, 20, 41, 42]   # frag_d*/mispredict_not_taken (300 ld, /work/stt scheme2) REAL race
STT_TK  = [0, 0, 2, 2]      # frag_d*/mispredict_taken
# Fence (SPT_6_oneLP, 150): RAW reached_cache = const-addr over-approx, NOT real leaks.
FENCE_NT_RAW = [50, 53, 41, 45]   # fence_d*/mispredict_not_taken (const-addr dominated)
FENCE_NT_REAL = [0, 0, 0, 0]      # tainted-address race at stock: 0/230 (claudelog 23:55)

# --- F8: AMuLeT vs SimSpect efficiency on the SAME SpecLFB build (UV6), MEASURED 2026-06-03 ----
# SimSpect: results/STT_6_speclfb (ordered 300-test sample) — first UV6 flag at test #6; yield 68/300=23%.
# AMuLeT:  results/STT_6_speclfb/amulet_compare/fuzz.log — cli.py fuzz --SpecLFB on the SpecLFB_AE build,
#   120 tests: first contract violation at test #39; 4 violations / 120 = 3.3%; --profile m5.simulate 6.8s.
# GEM5-ONLY time (the fair number — excludes our as+ld build AND the O3PipeView measurement trace):
#   SimSpect gem5 SIM hostSeconds = 0.092 s/test (LIGHT trace; /tmp/time_gem5_only.py, 6 tests).
#   AMuLeT  gem5 m5.simulate     = 6.8s/120     = 0.057 s/test (fuzz.log --profile).  → COMPARABLE (~1.6x).
#   SimSpect overhead that is NOT simulation: O3PipeView measurement trace +0.39 s/test (heavy sim 0.482
#   - light 0.092); fresh gem5 boot +~0.61 s/test (light wall 0.70 - sim 0.092) which AMuLeT amortizes via
#   persistent IPC. Both are harness/measurement, not gem5 work.
EFF = {
    "tests_to_first": {"SimSpect": 6,  "AMuLeT": 39},      # lower = better targeting
    "hit_density_pct":{"SimSpect": 23.0,"AMuLeT": 3.3},    # higher = denser signal
    "gem5_sim_sec":   {"SimSpect": 0.092,"AMuLeT": 0.057}, # PURE gem5 sim/test — comparable
}
# SimSpect per-test wall decomposition (s) — only "gem5 sim" is comparable to AMuLeT's 0.057 sim
SIM_DECOMP = [("gem5 sim", 0.092, "#2ca02c"), ("O3PipeView trace\n(measurement)", 0.39, "#ff7f0e"),
              ("gem5 boot\n(harness: no IPC)", 0.61, "#d4a017"), ("as+ld build", 0.03, "#9e9e9e")]
AMULET_PROFILE = [("gem5", 37.9), ("generation", 18.3), ("ctrace", 4.0),
                  ("parse", 2.8), ("priming", 7.7), ("other", 29.3)]  # % of 42.1s (fuzz.log --profile)


# =====================================================================================
# F1 — hit attribution per run (3 candidates)
# =====================================================================================
def f1a():
    """Candidate A: per-run log-scaled horizontal bars, colored by layer."""
    n = len(RUNS); fig, axes = plt.subplots(1, n, figsize=(20, 4.6))
    for ax, (label, bks, real, note) in zip(axes, RUNS):
        if not bks:
            ax.text(.5,.6,"0 hits",ha="center",fontsize=20,fontweight="bold",color=C_CLEAN)
            ax.text(.5,.4,"defense holds",ha="center",color=C_CLEAN)
            ax.set_xticks([]); ax.set_yticks([])
            for s in ax.spines.values(): s.set_color(C_CLEAN); s.set_linewidth(2)
        else:
            labs=[b[0] for b in bks]; cnts=[b[1] for b in bks]; cols=[b[2] for b in bks]
            y=range(len(bks)); ax.barh(list(y),cnts,color=cols,edgecolor="black",linewidth=.6)
            ax.set_yticks(list(y)); ax.set_yticklabels(labs,fontsize=8); ax.invert_yaxis()
            ax.set_xscale("log"); ax.set_xlim(.6,max(cnts)*4)
            for yi,c in zip(y,cnts):
                ax.text(c*1.2,yi,f"{c:,}",va="center",fontsize=8,fontweight="bold")
            ax.set_xlabel("hit records (log)",fontsize=8)
        ax.set_title(label,fontsize=8.5,fontweight="bold")
        ax.text(0,-0.32,note,transform=ax.transAxes,fontsize=7,va="top",color="#333333")
    leg=[Patch(facecolor=C_TARGET,label="TARGET — real defense bug"),
         Patch(facecolor=C_OPEN,label="TARGET candidate (open)"),
         Patch(facecolor=C_CHECKER,label="CHECKER artifact"),
         Patch(facecolor=C_ALLOY,label="ALLOY over-approx / concretization"),
         Patch(facecolor=C_CLEAN,label="defense holds (0 hits)")]
    fig.legend(handles=leg,loc="lower center",ncol=5,fontsize=8.5,bbox_to_anchor=(.5,-.06))
    fig.suptitle("F1a — SimSpect hits per (testset x defense), attributed by layer "
                 "(a hit = gem5 permits what the model forbids)",fontsize=12,fontweight="bold")
    fig.tight_layout(rect=[0,.02,1,.96]); save(fig,"F1_attribution_a.png")

def f1b():
    """Candidate B: triage 'funnel' — total hits collapse to real bugs, per run."""
    fig, ax = plt.subplots(figsize=(12,5.6))
    rows=[("Recon-STT\n(stock)",184,183,0,1),
          ("STT slow-comm\n(full)",19845+21+4122,21,4122,19845),
          ("SPT-Fence\n(slow-comm)",67297+5503+358+4397,67297+5503+358,4397,0),
          ("SPT-Fence\n(stock)",6118,6118,0,0),
          ("STT stock",0,0,0,0)]
    ylabels=[r[0] for r in rows]; y=range(len(rows))
    for yi,(_,tot,arti,opn,real) in zip(y,rows):
        if tot==0:
            ax.text(1,yi,"  0 hits — defense holds",va="center",color=C_CLEAN,fontweight="bold")
            continue
        ax.barh(yi,arti,color=C_ALLOY,edgecolor="k",label="model+checker artifact" if yi==0 else "")
        ax.barh(yi,opn,left=arti,color=C_OPEN,edgecolor="k",label="candidate (open)" if yi==0 else "")
        ax.barh(yi,max(real,tot*0.004),left=arti+opn,color=C_TARGET,edgecolor="k",
                label="REAL target bug" if yi==0 else "")
        ax.text(tot*1.02,yi,f"{tot:,} hits -> {real:,} real",va="center",fontsize=8.5,fontweight="bold")
    ax.set_yticks(list(y)); ax.set_yticklabels(ylabels,fontsize=9); ax.invert_yaxis()
    ax.set_xscale("symlog"); ax.set_xlabel("hit records (symlog)")
    ax.set_title("F1b — disqualifier funnel: raw hits collapse to confirmed real bugs\n"
                 "(model over-approx + checker FP filtered first; only survivors are real)",
                 fontsize=12,fontweight="bold")
    ax.legend(loc="lower right",fontsize=9)
    fig.tight_layout(); save(fig,"F1_attribution_b.png")

def f1c():
    """Candidate C: scoreboard table-figure (defense x outcome), real-bug cell highlit."""
    cols=["raw hits","model\nartifact","checker\nFP","candidate\n(open)","REAL\nbug"]
    rows=[("Recon-STT (stock)","184","—","183","0","1  (SLF/A2)"),
          ("STT (stock)","0","—","—","—","0 — holds"),
          ("STT (slow-comm)","23,988","—","21","4,122","19,845 (A4)"),
          ("SPT-Fence (stock)","6,118","6,111","7","0","0"),
          ("SPT-Fence (slow-comm)","77,555","73,158","—","4,397","0* (A5 open)")]
    fig,ax=plt.subplots(figsize=(12,3.4)); ax.axis("off")
    tbl=ax.table(cellText=[r[1:] for r in rows],rowLabels=[r[0] for r in rows],
                 colLabels=cols,cellLoc="center",rowLoc="center",loc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(9); tbl.scale(1,2.0)
    for (r,c),cell in tbl.get_celld().items():
        if r==0 or c==-1: cell.set_text_props(fontweight="bold")
        if c==4 and r>0:  # REAL bug column
            txt=rows[r-1][5]
            cell.set_facecolor("#fde0e0" if ("A2" in txt or "A4" in txt) else "#eeeeee")
            if "A2" in txt or "A4" in txt: cell.set_text_props(fontweight="bold",color=C_TARGET)
    ax.set_title("F1c — SimSpect scoreboard: every run's raw hits vs confirmed real defense bug\n"
                 "(*SPT-Fence slow-comm 'NEW' contains the ~983 VP-squash-race candidates shared with STT)",
                 fontsize=11.5,fontweight="bold",pad=14)
    fig.tight_layout(); save(fig,"F1_attribution_c.png")


# =====================================================================================
# F2 — AMuLeT bug scope (3 candidates)
# =====================================================================================
def f2a():
    """Candidate A: per-bug IN/OUT matrix with channel + reason."""
    fig,ax=plt.subplots(figsize=(13,5.2)); ax.axis("off")
    ax.set_xlim(0,10); ax.set_ylim(0,len(AMULET_BUGS)+1)
    ax.text(0.4,len(AMULET_BUGS)+0.4,"bug",fontweight="bold")
    ax.text(1.4,len(AMULET_BUGS)+0.4,"defense",fontweight="bold")
    ax.text(3.3,len(AMULET_BUGS)+0.4,"leakage channel",fontweight="bold")
    ax.text(7.0,len(AMULET_BUGS)+0.4,"SimSpect scope",fontweight="bold")
    for i,(bid,dfn,ch,ins,why) in enumerate(AMULET_BUGS):
        y=len(AMULET_BUGS)-1-i+0.5
        col=C_TARGET if ins else C_AMULET
        ax.add_patch(plt.Rectangle((0.2,y-0.36),9.6,0.72,facecolor=col,alpha=0.12,
                                   edgecolor=col,linewidth=1.4))
        ax.text(0.4,y,bid,fontweight="bold",va="center",color=col)
        ax.text(1.4,y,dfn,va="center",fontsize=9)
        ax.text(3.3,y,ch,va="center",fontsize=9)
        ax.text(6.6,y,("● IN" if ins else "○ OUT"),va="center",fontweight="bold",color=col)
        ax.text(7.3,y,why,va="center",fontsize=7.6,color="#333333")
    ax.set_title("F2a — the 8 AMuLeT-reported bugs vs SimSpect's leakage model\n"
                 "SimSpect sees a leak iff it is the TRANSMITTER's own access INSIDE the spec window\n"
                 "(1 of 8 in scope: SpecLFB UV6 — DEMONSTRATED, 68/300; only the end-to-end secret-recovery PoC pends a stimulus fix)",
                 fontsize=11.5,fontweight="bold")
    fig.tight_layout(); save(fig,"F2_scope_a.png")

def f2b():
    """Candidate B: bugs grouped by channel, shaded by which tool observes it."""
    chans=["D-cache line-fill\n(transmitter's own)","cache EVICTION\n(another line)",
           "MSHR\ncontention","L1I\nfetch","D-TLB\n(store xmit)","post-squash\nresidue"]
    counts=[1,1,1,1,1,3]; inscope=[True,False,False,False,False,False]
    fig,ax=plt.subplots(figsize=(11,5))
    bars=ax.bar(chans,counts,color=[C_TARGET if s else C_AMULET for s in inscope],
                edgecolor="black")
    for b,n,s in zip(bars,counts,inscope):
        ax.text(b.get_x()+b.get_width()/2,n+0.04,f"{n}",ha="center",fontweight="bold")
        ax.text(b.get_x()+b.get_width()/2,n/2,"SimSpect\n✓" if s else "AMuLeT\nonly",
                ha="center",va="center",color="white",fontsize=8,fontweight="bold")
    ax.set_ylabel("# AMuLeT bugs on this channel"); ax.set_ylim(0,3.6)
    ax.set_title("F2b — AMuLeT bugs by leakage channel — SimSpect observes only the\n"
                 "transmitter's own in-window D-cache line-fill (UV6); the rest are collateral resources",
                 fontsize=11.5,fontweight="bold")
    fig.tight_layout(); save(fig,"F2_scope_b.png")

def f2c():
    """Candidate C: 2x2 quadrant — observation channel x comparison method."""
    fig,ax=plt.subplots(figsize=(9.2,7.5)); ax.set_xlim(0,10); ax.set_ylim(0,10); ax.axis("off")
    ax.plot([5,5],[0,10],color="#999999",lw=1); ax.plot([0,10],[5,5],color="#999999",lw=1)
    ax.text(2.5,9.6,"TRANSMITTER's own access",ha="center",fontsize=10,fontweight="bold",color=C_TARGET)
    ax.text(7.5,9.6,"COLLATERAL shared resource",ha="center",fontsize=10,fontweight="bold",color=C_AMULET)
    ax.text(-0.2,7.5,"single run vs\nMODEL window",ha="center",va="center",rotation=90,fontsize=10,fontweight="bold")
    ax.text(-0.2,2.5,"input DIFFERENTIAL\nvs contract",ha="center",va="center",rotation=90,fontsize=10,fontweight="bold")
    # SimSpect quadrant (top-left)
    ax.add_patch(plt.Rectangle((0,5),5,5,facecolor=C_TARGET,alpha=0.10))
    ax.text(2.5,8.4,"SimSpect",ha="center",fontsize=13,fontweight="bold",color=C_TARGET)
    ax.text(2.5,7.0,"• VP↔squash race (A4/A5)\n• recon SLF (A2), OTB (A1)\n• SpecLFB UV6 (demonstrated)",
            ha="center",fontsize=9)
    # AMuLeT quadrant (bottom-right)
    ax.add_patch(plt.Rectangle((5,0),5,5,facecolor=C_AMULET,alpha=0.10))
    ax.text(7.5,3.4,"AMuLeT",ha="center",fontsize=13,fontweight="bold",color=C_AMULET)
    ax.text(7.5,2.0,"• L1D eviction (UV1)\n• MSHR (UV2), L1I (KV1)\n• STT store→TLB (KV3)\n• cleanup residue (UV3-5)",
            ha="center",fontsize=9)
    ax.text(7.5,7.5,"(targeted collateral —\nneither tool's sweet spot)",ha="center",fontsize=8,color="#888888",style="italic")
    ax.text(2.5,2.5,"UV6 (SpecLFB): DEMONSTRATED —\nfirst spec load unprotected,\naccesses cache in-window (68/300);\nonly secret-recovery PoC pends stimulus",
            ha="center",fontsize=8,color="#555555",style="italic")
    ax.set_title("F2c — what each tool targets — observation channel × comparison method",
                 fontsize=12,fontweight="bold")
    fig.tight_layout(); save(fig,"F2_scope_c.png")


# =====================================================================================
# F3 — test targeting / diversity (3 candidates)
# =====================================================================================
def f3a():
    """Candidate A: normalized stacked bars — % of generated tests that can even leak."""
    fig,ax=plt.subplots(figsize=(8,5.4))
    tools=["AMuLeT STT corpus\n(random, n=500)","SimSpect STT_6\n(targeted, n=100,000)"]
    can =[AMULET_EITHER/AMULET_N*100, 100.0]
    cant=[100-can[0], 0.0]
    ax.bar(tools,can,color=C_TARGET,edgecolor="k",label="contains a leakable transmitter gadget")
    ax.bar(tools,cant,bottom=can,color="#d9d9d9",edgecolor="k",label="cannot leak by construction")
    for i,c in enumerate(can):
        ax.text(i,c/2,f"{c:.0f}%",ha="center",va="center",color="white",fontweight="bold",fontsize=13)
        if cant[i]>2: ax.text(i,c+cant[i]/2,f"{cant[i]:.0f}%",ha="center",va="center",fontweight="bold")
    ax.set_ylabel("% of generated tests"); ax.set_ylim(0,100)
    ax.set_title("F3a — test targeting: fraction of generated tests that can even leak\n"
                 "AMuLeT 17% (85/500, static gadget analysis) vs SimSpect 100% (tag_xm by construction)",
                 fontsize=11.5,fontweight="bold")
    ax.legend(loc="center right",fontsize=9)
    fig.tight_layout(); save(fig,"F3_targeting_a.png")

def f3b():
    """Candidate B: AMuLeT gadget breakdown (tight vs loose) + SimSpect 100% reference."""
    fig,ax=plt.subplots(figsize=(9.5,5.2))
    cats=["LL (load→load)","BRX (branch)","EITHER"]
    tight=[AMULET_LL/AMULET_N*100, AMULET_BRX/AMULET_N*100, AMULET_EITHER/AMULET_N*100]
    loose=[AMULET_LL_LOOSE/AMULET_N*100, AMULET_BRX_LOOSE/AMULET_N*100, AMULET_EITHER_LOOSE/AMULET_N*100]
    x=range(len(cats)); w=0.38
    ax.bar([i-w/2 for i in x],loose,w,color="#bbccdd",edgecolor="k",label="structure only (loose)")
    ax.bar([i+w/2 for i in x],tight,w,color=C_AMULET,edgecolor="k",label="window+unprotected+fence (tight)")
    for i,(t,l) in enumerate(zip(tight,loose)):
        ax.text(i-w/2,l+1,f"{l:.0f}%",ha="center",fontsize=8)
        ax.text(i+w/2,t+1,f"{t:.0f}%",ha="center",fontsize=8,fontweight="bold")
    ax.axhline(100,color=C_TARGET,lw=2,ls="--")
    ax.text(len(cats)-1,96,"SimSpect = 100% (every test targeted)",ha="right",color=C_TARGET,fontweight="bold")
    ax.set_xticks(list(x)); ax.set_xticklabels(cats); ax.set_ylabel("% of AMuLeT's 500 tests")
    ax.set_ylim(0,108)
    ax.set_title("F3b — AMuLeT STT corpus: how many random tests contain a real speculative gadget\n"
                 "even loose structural matches top out at 70%; window-valid gadgets only 17%",
                 fontsize=11,fontweight="bold")
    ax.legend(loc="upper left",fontsize=9)
    fig.tight_layout(); save(fig,"F3_targeting_b.png")

def f3c():
    """Candidate C: paired donuts — 'yield' of leakable tests per generator."""
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    specs=[("AMuLeT (random)",AMULET_EITHER,AMULET_N-AMULET_EITHER,
            f"{AMULET_EITHER}/{AMULET_N}\n= 17%"),
           ("SimSpect (targeted)",SIMSPECT_N,0,f"{SIMSPECT_N:,}/{SIMSPECT_N:,}\n= 100%")]
    for ax,(title,can,cant,center) in zip(axes,specs):
        ax.pie([can,max(cant,0.0001)],colors=[C_TARGET,"#e3e3e3"],startangle=90,counterclock=False,
               wedgeprops=dict(width=0.42,edgecolor="white"))
        ax.text(0,0,center,ha="center",va="center",fontsize=12,fontweight="bold")
        ax.set_title(title,fontsize=12,fontweight="bold")
    fig.suptitle("F3c — leakable-test YIELD per generator (red = test can exhibit a speculative leak)",
                 fontsize=12,fontweight="bold")
    fig.tight_layout(); save(fig,"F3_targeting_c.png")


# =====================================================================================
# F4 — stall-knob sensitivity (3 candidates)
# =====================================================================================
def f4a():
    """Candidate A: 3 separate panels (s_U log, s_R, fnc) — the clean curves."""
    fig,axs=plt.subplots(1,3,figsize=(13,4))
    panels=[("s_U  unresolved-branch stall",SU_X,SU_Y,True,
             "MASKS the leak:\nany s_U≥50 → 0"),
            ("s_R  resolved-branch stall",SR_X,SR_Y,False,
             "≈flat plateau\n(27→22)"),
            ("fnc  fnc-commit stall",FNC_X,FNC_Y,False,
             "leak survives at\nfnc=0 (16); plateaus")]
    for ax,(title,x,y,logx,txt) in zip(axs,panels):
        xp=[max(v,1) for v in x] if logx else x
        ax.plot(xp,y,"-o",color=C_TARGET,lw=2,ms=7)
        if logx: ax.set_xscale("log"); ax.set_xlabel("stall cycles (log; 0 at 1)")
        else: ax.set_xlabel("stall cycles")
        ax.set_ylim(0,30); ax.grid(alpha=.3); ax.set_title(title,fontsize=10.5,fontweight="bold")
        ax.text(0.96,0.92,txt,transform=ax.transAxes,ha="right",va="top",fontsize=8.5,
                bbox=dict(boxstyle="round",fc="#fff3cd",ec="#d4a017"))
    axs[0].set_ylabel("real cache-access leaks (of 200)")
    fig.suptitle("F4a — STT stall sensitivity @ commitToIEWDelay=3 — 100% bucket-confirmed VP-squash race\n"
                 "validates the harness: only the WINDOW knob (s_U) changes the verdict; it MASKS (never manufactures)",
                 fontsize=11,fontweight="bold",y=1.04)
    fig.tight_layout(); save(fig,"F4_stalls_a.png")

def f4b():
    """Candidate B: normalized overlay — each knob vs its own sweep, % of baseline=27."""
    fig,ax=plt.subplots(figsize=(8.6,5))
    base=27.0
    ax.plot(range(len(SU_X)),[v/base*100 for v in SU_Y],"-o",color=C_TARGET,lw=2,label="s_U (unresolved)")
    ax.plot(range(len(SR_X)),[v/base*100 for v in SR_Y],"-s",color="#2980b9",lw=2,label="s_R (resolved)")
    ax.plot(range(len(FNC_X)),[v/base*100 for v in FNC_Y],"-^",color="#d4a017",lw=2,label="fnc")
    ax.set_xlabel("sweep index (low → high stall)"); ax.set_ylabel("leaks as % of baseline (27)")
    ax.axhline(100,color="#999999",ls=":"); ax.set_ylim(-5,115)
    ax.set_title("F4b — normalized stall sensitivity — s_U is the ONLY knob that\n"
                 "collapses the leak to 0 (masks the window); s_R/fnc stay on a plateau",
                 fontsize=11,fontweight="bold")
    ax.legend(fontsize=9.5); ax.grid(alpha=.3)
    fig.tight_layout(); save(fig,"F4_stalls_b.png")

def f4c():
    """Candidate C: tornado — leak swing from baseline across each knob's full range."""
    fig,ax=plt.subplots(figsize=(8.6,3.6))
    base=27
    knobs=["s_U: 0 → 5000","fnc: 150 → 0","s_R: 0 → 64"]
    lows =[min(SU_Y), min(FNC_Y), min(SR_Y)]   # extreme value reached
    swings=[base-l for l in lows]
    cols=[C_TARGET,"#d4a017","#2980b9"]
    ax.barh(knobs,swings,color=cols,edgecolor="k")
    for i,(s,l) in enumerate(zip(swings,lows)):
        ax.text(s+0.3,i,f"−{s}  (to {l})",va="center",fontsize=9,fontweight="bold")
    ax.set_xlabel("reduction in real leak count from baseline (27)")
    ax.set_xlim(0,30); ax.invert_yaxis()
    ax.set_title("F4c — stall-knob 'tornado': s_U erases ALL 27 leaks (full mask);\n"
                 "fnc removes 11 (leak persists at 0); s_R barely moves it",
                 fontsize=10.5,fontweight="bold")
    fig.tight_layout(); save(fig,"F4_stalls_c.png")


# =====================================================================================
# F5 — fragility threshold (3 candidates)
# =====================================================================================
def f5a():
    """Candidate A: STT fragility curve, both modes, stock-control highlighted."""
    fig,ax=plt.subplots(figsize=(7.6,5))
    ax.axvspan(0.9,1.1,color="green",alpha=.08)
    ax.plot(FRAG_D,STT_NT,"-o",color="#c0392b",lw=2,ms=7,label="mispred. not_taken (300)")
    ax.plot(FRAG_D,STT_TK,"-s",color="#2980b9",lw=2,ms=7,label="mispred. taken (300)")
    ax.annotate("stock = 0\n(control: defense holds)",(1,0),textcoords="offset points",
                xytext=(10,28),fontsize=8.5,color="green",
                arrowprops=dict(arrowstyle="->",color="green"))
    ax.annotate("threshold\nd=2",(2,20),textcoords="offset points",xytext=(6,-2),fontsize=8.5)
    ax.set_xticks(FRAG_D); ax.set_xlabel("commitToIEWDelay (squash→IEW propagation, cycles)")
    ax.set_ylabel("real cache-access leaks (of 300)")
    ax.set_title("F5a — STT fragility threshold (release↔squash race)\n"
                 "/work/stt scheme2, bare timing — 0 at stock, climbs once squash latency ≥2",
                 fontsize=11,fontweight="bold")
    ax.grid(alpha=.3); ax.legend()
    fig.tight_layout(); save(fig,"F5_fragility_a.png")

def f5b():
    """Candidate B: STT vs Fence control — raw cache-reach vs real (filtered) leaks."""
    fig,ax=plt.subplots(figsize=(8.6,5.2))
    ax.plot(FRAG_D,STT_NT,"-o",color=C_TARGET,lw=2,ms=7,label="STT — REAL leaks (tainted addr)")
    ax.plot(FRAG_D,FENCE_NT_RAW,"--D",color="#999999",lw=1.8,ms=6,
            label="Fence — RAW cache-reach (const-addr over-approx, NOT leaks)")
    ax.plot(FRAG_D,FENCE_NT_REAL,"-s",color=C_CLEAN,lw=2,ms=7,
            label="Fence — REAL leaks after const-addr filter (control = 0)")
    ax.set_xticks(FRAG_D); ax.set_xlabel("commitToIEWDelay (cycles)")
    ax.set_ylabel("ld leaks per sample (STT/300, Fence/150)")
    ax.set_title("F5b — fragility: STT vs Fence control — why the raw metric needs the\n"
                 "model-artifact filter (Fence's ~33% 'cache-reach' is const-addr, not a leak)",
                 fontsize=10.8,fontweight="bold")
    ax.grid(alpha=.3); ax.legend(fontsize=8.5,loc="center right")
    fig.tight_layout(); save(fig,"F5_fragility_b.png")

def f5c():
    """Candidate C: fragility 'threshold bar' — smallest commitToIEWDelay with real leaks."""
    fig,ax=plt.subplots(figsize=(8.2,3.4))
    defs=["STT (load fence)","SPT-Fence (DDIFT)","Fence @ stock (control)"]
    thr =[2, 99, 99]   # 99 = no real leak in the stock-feasible range (race only under slow-comm)
    labels=["leaks at commitToIEWDelay ≥ 2","no STOCK leak; same race only\nunder slow-comm (A5, open)",
            "0 at every value (after\nconst-addr filter)"]
    cols=[C_TARGET,C_OPEN,C_CLEAN]
    bars=ax.barh(defs,[min(t,4.3) for t in thr],color=cols,edgecolor="k")
    for i,(t,lab) in enumerate(zip(thr,labels)):
        ax.text(0.15,i,lab,va="center",fontsize=8.5,color="white" if i==0 else "black",fontweight="bold")
    ax.set_xlim(0,4.5); ax.set_xlabel("commitToIEWDelay fragility threshold (lower = more fragile)")
    ax.invert_yaxis()
    ax.set_title("F5c — fragility ranking: smallest squash-latency at which each defense leaks\n"
                 "(STT is the most fragile: a single realistic timing bump breaks it)",
                 fontsize=10.5,fontweight="bold")
    fig.tight_layout(); save(fig,"F5_fragility_c.png")


# =====================================================================================
# F6 — VP↔squash race mechanism (timeline schematic)
# =====================================================================================
def f6():
    fig,ax=plt.subplots(figsize=(13,5.4)); ax.set_xlim(0,13); ax.set_ylim(0,6.2); ax.axis("off")
    YL=1.0   # timeline y
    # timeline axis
    ax.annotate("",xy=(12.7,YL),xytext=(0.3,YL),arrowprops=dict(arrowstyle="->",lw=1.6))
    ax.text(12.7,YL-0.32,"tick →",fontsize=9)
    # events (inst-000005 slow-comm, claudelog 23:55 / 00:20): (x, text, color, label_above?)
    evs=[(1.8,"data ready\n@2932500","#555555",True),
         (5.4,"branch RESOLVES\n= visibility point @2945500",C_OPEN,False),
         (7.4,"taint cleared\n(isPrevBrsResolved)\n→ xmit untainted",C_TARGET,True),
         (9.4,"cache PACKET\n@2946500",C_TARGET,False),
         (11.2,"squash drains\nto LSQ @2947500","#2980b9",True)]
    for x,t,c,above in evs:
        ax.add_patch(plt.Circle((x,YL),0.07,color=c,zorder=5))
        if above:
            ax.plot([x,x],[YL,YL+0.22],color=c,lw=1.5)
            ax.text(x,YL+0.30,t,ha="center",va="bottom",fontsize=8.4,color=c,fontweight="bold")
        else:
            ax.plot([x,x],[YL-0.22,YL],color=c,lw=1.5)
            ax.text(x,YL-0.32,t,ha="center",va="top",fontsize=8.4,color=c,fontweight="bold")
    # the "held / fenced" span (data-ready -> VP)
    ax.add_patch(FancyBboxPatch((1.8,3.1),3.6,0.62,boxstyle="round,pad=0.02",fc="#d6eaf8",ec="#2980b9"))
    ax.text(3.6,3.41,"xmit HELD (tainted / fenced)\ndefense working",ha="center",va="center",fontsize=8.4)
    # the leak gap (VP -> squash-drain)
    ax.add_patch(plt.Rectangle((5.4,2.78),5.8,0.30,color=C_TARGET,alpha=0.22))
    ax.annotate("",xy=(11.2,2.93),xytext=(5.4,2.93),arrowprops=dict(arrowstyle="<->",color=C_TARGET,lw=1.6))
    ax.text(8.3,3.20,"[VP → squash-drain] GAP  =  wrong-path xmit touches cache (LEAK)",
            ha="center",va="bottom",fontsize=9.5,color=C_TARGET,fontweight="bold")
    # the logic box
    ax.add_patch(FancyBboxPatch((0.4,4.3),12.2,1.25,boxstyle="round,pad=0.03",fc="#fdecea",ec=C_TARGET))
    ax.text(6.5,5.18,"THE BAD LOGIC (shared by STT A4 and SPT-Fence A5):",ha="center",fontweight="bold",
            color=C_TARGET,fontsize=10.5)
    ax.text(6.5,4.66,"untaint condition = isPrevBrsResolved   — clears protection at branch RESOLUTION,\n"
            "with NO guard excluding instructions that are themselves on the to-be-squashed wrong path.",
            ha="center",fontsize=9)
    ax.text(6.5,0.12,"commitToIEWDelay only sets the GAP WIDTH; the flaw is the missing 'not-on-squashed-path' guard.   "
            "Stock(=1): squash wins.   ≥2–3 cyc: packet wins.",ha="center",fontsize=8,style="italic",color="#444444")
    ax.set_title("F6 — the visibility-point ↔ squash race (STT == SPT-Fence): a logic flaw, timing-sized",
                 fontsize=12.5,fontweight="bold",pad=10)
    fig.tight_layout(); save(fig,"F6_vp_squash_race.png")


# =====================================================================================
# F7 — the two recon bugs (gadget schematics)
# =====================================================================================
def f7():
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    # --- OTB ---
    ax=axes[0]; ax.set_xlim(0,10); ax.set_ylim(0,10); ax.axis("off")
    ax.set_title("A1 — recon OTB (getOldestTaint picks WRONG source)",fontsize=11,fontweight="bold",color=C_TARGET)
    def box(ax,x,y,w,h,t,c="#eeeeee",tc="black",fs=8.3):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.02",fc=c,ec="#444444"))
        ax.text(x+w/2,y+h/2,t,ha="center",va="center",fontsize=fs,color=tc)
    box(ax,0.5,8.3,9,1,"branch_outer (resolves FIRST, correctly not-taken)","#eeeeee")
    box(ax,1.0,6.8,3.6,1,"load_A → %rax\n(tainted, older)","#d6eaf8")
    box(ax,5.4,6.8,3.6,1,"load_B → %rcx\n(tainted, YOUNGER, still spec)","#d6eaf8")
    box(ax,2.5,5.0,5,1,"leaq (%rax,%rcx),%rax\ngetOldestTaint → keeps load_A only",C_OPEN,"white")
    box(ax,2.5,3.2,5,1,"branch_outer resolves → freeTaints drops %rax taint\n(but load_B still speculative!)","#fdecea")
    box(ax,2.5,1.4,5,1,"movq (%rcx,%rax),%rax  TRANSMITTER\naddress 'untainted' → cache access",C_TARGET,"white")
    for (x0,y0,x1,y1) in [(2.8,6.8,3.5,6.0),(7.2,6.8,6.5,6.0),(5,5.0,5,4.2),(5,3.2,5,2.4)]:
        ax.annotate("",xy=(x1,y1),xytext=(x0,y0),arrowprops=dict(arrowstyle="->",color="#666666"))
    ax.text(5,0.5,"verdict: REAL bug (taint tracker keeps oldest, not youngest); generator can't\n"
            "reach it yet (C3 OTB gen-gap) → demonstrated hand-crafted",ha="center",fontsize=7.6,style="italic")
    # --- STL/SLF ---
    ax=axes[1]; ax.set_xlim(0,10); ax.set_ylim(0,10); ax.axis("off")
    ax.set_title("A2 — recon STL/SLF (store-forward bypasses taint check)",fontsize=11,fontweight="bold",color=C_TARGET)
    box(ax,0.5,8.3,9,1,"je end — MISPREDICT → speculative window opens","#eeeeee")
    box(ax,2.5,6.6,5,1,"movq (%rsi),%rax → %rax TAINTED (spec load)","#d6eaf8")
    box(ax,2.5,4.9,5,1,"movq %r8,(%rsi,%rax) — store to tainted address","#fff3cd")
    box(ax,2.5,3.0,5,1.1,"movq (%rsi,%rax),%r10  TRANSMITTER\nLSQ store-forwards → returns NoFault\nBEFORE the STT taint check (line 2090)",C_TARGET,"white")
    for (x0,y0,x1,y1) in [(5,8.3,5,7.6),(5,6.6,5,5.9),(5,4.9,5,4.1)]:
        ax.annotate("",xy=(x1,y1),xytext=(x0,y0),arrowprops=dict(arrowstyle="->",color="#666666"))
    ax.text(5,1.9,"completes (ready-in-ROB @2682500) BEFORE squash @2683500,\nwith NO cache packet — the SLF leak bar",
            ha="center",fontsize=8,color=C_TARGET)
    ax.text(5,0.7,"verdict: REAL bug, caught LIVE from generator output (inst-014912) —\n"
            "the only confirmed real leak among Recon_6's 184 ld hits; 'the big unknown'",
            ha="center",fontsize=7.6,style="italic")
    fig.suptitle("F7 — the two recon STT bugs SimSpect targets",fontsize=13,fontweight="bold",y=1.05)
    fig.tight_layout(rect=[0,0,1,0.95]); save(fig,"F7_recon_bugs.png")


C_SIM = "#2ca02c"; C_AML = C_AMULET   # SimSpect green, AMuLeT brown

def f8a():
    """Candidate A: 3-panel efficiency — tests-to-first, hit-density, per-test cost (all MEASURED)."""
    fig,axs=plt.subplots(1,3,figsize=(13.5,4.2))
    panels=[("tests to FIRST detection","tests_to_first","# test cases (lower = better targeting)",False),
            ("hit density","hit_density_pct","% of tests that flag UV6 (higher = denser)",False),
            ("gem5 SIM time / test","gem5_sim_sec","seconds, pure simulation (lower = faster)",False)]
    for ax,(title,key,ylab,logy) in zip(axs,panels):
        d=EFF[key]; tools=["SimSpect","AMuLeT"]; vals=[d[t] for t in tools]
        bars=ax.bar(tools,vals,color=[C_SIM,C_AML],edgecolor="black")
        for b,v in zip(bars,vals):
            ax.text(b.get_x()+b.get_width()/2,v*1.02,(f"{v:g}"),ha="center",fontweight="bold")
        ax.set_title(title,fontsize=10.5,fontweight="bold"); ax.set_ylabel(ylab,fontsize=8.5)
    axs[0].annotate("6.5× fewer",(0,6),textcoords="offset points",xytext=(8,20),fontsize=8.5,color=C_SIM,fontweight="bold")
    axs[2].set_ylim(0,0.12)
    axs[2].text(0.5,0.105,"COMPARABLE (~1.6×)\nonce our O3PipeView trace\n+ per-test gem5 boot are\nexcluded (both instrumentation)",
                ha="center",va="top",fontsize=7.3,color="#333333",
                bbox=dict(boxstyle="round",fc="#eaffea",ec="#2ca02c"))
    fig.suptitle("F8a — AMuLeT vs SimSpect on the SAME SpecLFB build (UV6), MEASURED\n"
                 "SimSpect wins TARGETING (6 vs 39 tests, 23% vs 3.3%); gem5 SIMULATION cost is COMPARABLE (0.092 vs 0.057 s/test)",
                 fontsize=10.8,fontweight="bold",y=1.05)
    fig.tight_layout(rect=[0,0,1,0.94]); save(fig,"F8_efficiency_a.png")

def f8b():
    """Candidate B: per-test cost DECOMPOSITION — only the gem5-sim core is comparable; the rest is instrumentation."""
    fig,ax=plt.subplots(figsize=(9,5))
    # SimSpect stacked
    bottom=0
    for lab,val,col in SIM_DECOMP:
        ax.bar(["SimSpect"],[val],bottom=[bottom],color=col,edgecolor="black",label=lab)
        ax.text(0,bottom+val/2,f"{val:g}s",ha="center",va="center",fontsize=8,
                color="white" if col!="#9e9e9e" else "black",fontweight="bold")
        bottom+=val
    ax.text(0,bottom+0.03,f"wall {bottom:.2f}s/test",ha="center",fontweight="bold",fontsize=9)
    # AMuLeT (gem5 sim only — its generation/parse are separate; the comparable core is m5.simulate)
    ax.bar(["AMuLeT"],[EFF["gem5_sim_sec"]["AMuLeT"]],color=C_SIM,edgecolor="black")
    ax.text(1,EFF["gem5_sim_sec"]["AMuLeT"]+0.02,f"gem5 sim {EFF['gem5_sim_sec']['AMuLeT']:g}s",ha="center",fontweight="bold",fontsize=9)
    ax.annotate("same gem5 work\n(0.092 vs 0.057s)",xy=(1,0.057),xytext=(0.5,0.85),
                textcoords=("data","axes fraction"),ha="center",fontsize=8.5,color="#2ca02c",fontweight="bold",
                arrowprops=dict(arrowstyle="->",color="#2ca02c"))
    ax.set_ylabel("seconds per test"); ax.legend(fontsize=8,loc="upper right")
    ax.set_title("F8b — 'just the gem5 time' is COMPARABLE — SimSpect's extra per-test cost is\n"
                 "the O3PipeView measurement trace + fresh gem5 boot (both harness/instrumentation, removable)",
                 fontsize=10.5,fontweight="bold")
    fig.tight_layout(); save(fig,"F8_efficiency_b.png")

def f8c():
    """Candidate C: AMuLeT executor per-stage profile (the 42.1s breakdown) + the targeting headline."""
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(12,4.6),gridspec_kw={"width_ratios":[1.1,1]})
    labs=[p[0] for p in AMULET_PROFILE]; vals=[p[1] for p in AMULET_PROFILE]
    ax1.pie(vals,labels=labs,autopct="%.0f%%",startangle=90,counterclock=False,
            colors=["#8c564b","#1f77b4","#ff7f0e","#2ca02c","#d4a017","#cccccc"],textprops={"fontsize":8})
    ax1.set_title("AMuLeT executor profile (42.1s/120 tests)\ngem5 dominates; generation 18%",fontsize=10,fontweight="bold")
    tools=["SimSpect","AMuLeT"]; tf=[EFF["tests_to_first"][t] for t in tools]
    ax2.barh(tools,tf,color=[C_SIM,C_AML],edgecolor="black")
    for i,v in enumerate(tf): ax2.text(v+0.6,i,f"{v} tests",va="center",fontweight="bold")
    ax2.set_xlabel("test cases to FIRST UV6 detection"); ax2.invert_yaxis(); ax2.set_xlim(0,45)
    ax2.set_title("targeting: SimSpect flags UV6 6.5× sooner\n(every test is the gadget vs 17% random yield)",fontsize=10,fontweight="bold")
    fig.suptitle("F8c — efficiency on the SpecLFB build (UV6): AMuLeT executor cost (left) + the targeting result (right)",
                 fontsize=10.5,fontweight="bold",y=1.04)
    fig.tight_layout(rect=[0,0,1,0.93]); save(fig,"F8_efficiency_c.png")


# ===== F9 — the big bug table grouped by defense (preview PNG; full = figures.tex) =====
# (defense-group, [ (bug, first_known, found_by, found_color, scope, verdict, verdict_color) ])
BUGTBL = [
 ("Recon-STT  (gem5-recon-modded, scheme 2)", [
   ("OTB — getOldestTaint keeps the OLDEST taint source","This work (reconresults.md)","SimSpect (hand-crafted¹)",C_CLEAN,"✗ gen-gap","real",C_TARGET),
   ("STL/SLF — store-forward bypasses the taint check","This work (reconresults.md)","SimSpect — LIVE (inst-014912)",C_CLEAN,"✓","real",C_TARGET)]),
 ("STT  (/work/stt · amulet STT_AE)", [
   ("Visibility-point↔squash race (load channel)","This work (slow-comm)","SimSpect — live (timing)",C_CLEAN,"✓","real",C_TARGET),
   ("Implicit-channel (branch) defense non-functional","This work (source audit²)","SimSpect (source-audited)",C_CLEAN,"~³","real (src)",C_TARGET),
   ("Tainted spec STORE → D-TLB entry (KV3)","DOLMA (prior); via AMuLeT","AMuLeT",C_AMULET,"✗ store/TLB","real (known)",C_TARGET)]),
 ("SPT-Fence  (gem5-spt, DDIFT)", [
   ("Visibility-point↔squash race (= STT class)","This work","SimSpect — live (timing)",C_CLEAN,"✓","candidate",C_OPEN),
   ("(no independent SPT bug — rest is model over-approx)","—","—","#999999","—","—","#999999")]),
 ("InvisiSpec  (amulet InvisiSpec_AE)", [
   ("Spec-load L1D EVICTION of a conflicting line (UV1)","AMuLeT (headline)","AMuLeT",C_AMULET,"✗ eviction","real",C_TARGET),
   ("Single-thread MSHR interference (UV2)","AMuLeT (ext. Behnia)","AMuLeT",C_AMULET,"✗ MSHR","real",C_TARGET),
   ("L1I speculative fetch (KV1)","Known (IS authors)","AMuLeT",C_AMULET,"✗ I-cache","real (known)",C_TARGET)]),
 ("CleanupSpec  (amulet CleanupSpec_AE)", [
   ("Spec store not cleaned on squash (UV3)","AMuLeT","AMuLeT",C_AMULET,"✗ residue","real",C_TARGET),
   ("Cacheline-split request not cleaned (UV4)","AMuLeT","AMuLeT",C_AMULET,"✗ residue","real",C_TARGET),
   ("Over-cleaning evicts a non-spec line (UV5)","AMuLeT","AMuLeT",C_AMULET,"✗ final-state","real",C_TARGET)]),
 ("SpecLFB  (amulet SpecLFB_AE)", [
   ("First speculative load left unprotected (UV6)","AMuLeT","BOTH — AMuLeT t39 · SimSpect t6/23%","#7a3fa0","✓","real",C_TARGET)]),
]
def f9_bug_table():
    rows=[]
    for grp,bugs in BUGTBL:
        rows.append(("__grp__",grp)); rows.extend(("bug",b) for b in bugs)
    H=len(rows); fig,ax=plt.subplots(figsize=(17,0.5*H+1.4)); ax.axis("off")
    ax.set_xlim(0,1); ax.set_ylim(0,H+0.5)
    # columns: x positions
    cx=[0.005,0.345,0.560,0.800,0.880]  # Bug, First-known, Found-by, Scope, Verdict
    heads=["Bug","First known from","Found by","Scope","Verdict"]
    ytop=H
    for x,h in zip(cx,heads): ax.text(x,ytop+0.15,h,fontweight="bold",fontsize=10,va="bottom")
    ax.plot([0,1],[ytop,ytop],color="black",lw=1.2)
    y=ytop
    for kind,payload in rows:
        y-=1
        if kind=="__grp__":
            ax.add_patch(plt.Rectangle((0,y),1,1,facecolor="#e8e8e8",edgecolor="white"))
            ax.text(0.005,y+0.5,"▸ "+payload,fontweight="bold",fontsize=9.5,va="center")
        else:
            bug,fk,fb,fbc,sc,vd,vdc=payload
            ax.text(cx[0],y+0.5,bug,fontsize=8.2,va="center")
            ax.text(cx[1],y+0.5,fk,fontsize=8.0,va="center",color="#333333")
            ax.text(cx[2],y+0.5,fb,fontsize=8.0,va="center",color=fbc,fontweight="bold")
            ax.text(cx[3],y+0.5,sc,fontsize=8.0,va="center")
            ax.text(cx[4],y+0.5,vd,fontsize=8.2,va="center",color=vdc,fontweight="bold")
            ax.plot([0,1],[y,y],color="#dddddd",lw=0.5)
    ax.text(0,-0.6,"¹ real but generator can't emit the ld→other→xm precursor (cap artifact C3) — hand-crafted.   "
            "² pending-squash sub-race fixed upstream (Mosier, master).   ³ live br_x ‘leaks’ were the check_br FP (B2, fixed); "
            "A3 is a real source-level gap not yet a live generated leak.",
            fontsize=7,va="top",color="#444444")
    ax.set_title("F9 — speculative-execution defense bugs by defense: provenance, which tool finds it, SimSpect scope, verdict\n"
                 "(Found-by: green=SimSpect · brown=AMuLeT · purple=Both;  full LaTeX version = paper_figures/figures.tex Table 1)",
                 fontsize=12,fontweight="bold")
    save(fig,"F9_bug_table.png")


if __name__ == "__main__":
    for fn in (f1a,f1b,f1c, f2a,f2b,f2c, f3a,f3b,f3c, f4a,f4b,f4c, f5a,f5b,f5c, f6, f7, f8a,f8b,f8c, f9_bug_table):
        try:
            fn()
        except Exception as e:
            import traceback; print("FAILED", fn.__name__, e); traceback.print_exc()
