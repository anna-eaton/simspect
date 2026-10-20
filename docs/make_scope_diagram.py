#!/usr/bin/env python3
"""Slide-ready figure: transmitter-gate (in scope) vs footprint-hiding (out of scope).
Renders docs/scope_diagram.png. See docs/AMULET_VS_SIMSPECT_SCOPE.md."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

GREEN="#2e7d32"; GREENF="#e8f5e9"; RED="#c62828"; REDF="#fdecea"
BLUE="#1565c0"; BLUEF="#e3f2fd"; GREY="#555555"; DARK="#222222"

fig, ax = plt.subplots(figsize=(13, 6.6))
ax.set_xlim(0, 130); ax.set_ylim(0, 66); ax.axis("off")

def box(x, y, w, h, text, fc, ec, fs=10, weight="normal", tc=DARK, r=0.04):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.3,rounding_size={r*100}",
                 fc=fc, ec=ec, lw=1.8))
    ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=fs, weight=weight, color=tc, wrap=True)

def arrow(x1,y1,x2,y2, c=GREY, lw=2, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2), arrowstyle=style, mutation_scale=16,
                 color=c, lw=lw, shrinkA=2, shrinkB=2))

ax.text(65, 63.5, "What SimSpect's oracle measures — and why InvisiSpec is out of scope",
        ha="center", fontsize=14, weight="bold", color=DARK)

# ---- the leak pipeline (left → right) ----
y=44
box(2, y, 17, 9, "Secret /\nspeculative\noperand", "#ffffff", GREY, 10, "bold")
box(23, y, 17, 9, "Dataflow\n(taint chain)", "#ffffff", GREY, 10)
box(44, y, 19, 9, "TRANSMITTER\ninstruction\n(load / branch)", BLUEF, BLUE, 10.5, "bold", BLUE)
# channels cluster
chs=["L1 tag","LRU/repl","MSHR/TBE","L2","Dir/coh","TLB","L1I","undo/cleanup"]
cx, cy, cw, chh = 80, 38, 21, 4.0
ax.add_patch(FancyBboxPatch((cx-2.5, cy-2.5), cw+5, chh*4+6.5, boxstyle="round,pad=0.3,rounding_size=3",
             fc=REDF, ec=RED, lw=1.6, linestyle="--"))
ax.text(cx+cw/2-1, cy+chh*4+3.0, "µarch channels (open-ended)", ha="center", fontsize=9.5, weight="bold", color=RED)
for i,c in enumerate(chs):
    col=i%2; row=i//2
    box(cx + col*(cw/2), cy + (3-row)*chh, cw/2-1.0, chh-0.8, c, "#ffffff", RED, 8.2, tc=RED, r=0.06)
box(110, y, 17, 9, "Attacker\nobserves", "#ffffff", GREY, 10, "bold")

arrow(19, y+4.5, 23, y+4.5)
arrow(40, y+4.5, 44, y+4.5)
arrow(63, y+4.5, 70, y+4.5)            # transmitter -> channels
arrow(101.5, y+4.5, 110, y+4.5)        # channels -> attacker

# ---- SimSpect oracle: at the transmitter (green) ----
arrow(53.5, y, 53.5, 30, c=GREEN, lw=2.4)
box(34, 22, 39, 7.5, "SimSpect ORACLE  ✓ in scope\n\"did the TRANSMITTER fire in the window?\"  (channel-agnostic, single-run)",
    GREENF, GREEN, 9.6, "bold", GREEN)
# gate marker on transmitter
ax.text(53.5, 54.2, "▲ transmitter-blocking defenses act HERE", ha="center", fontsize=9, weight="bold", color=GREEN)

# ---- AMuLeT oracle: at the channels (red) ----
arrow(90.5, cy-2.5, 90.5, 18, c=RED, lw=2.4, style="-|>")
box(70, 10.5, 41, 7.5, "AMuLeT ORACLE  (needed for footprint-hiding)\nwhole-µarch state, DIFFERENTIAL across runs, per-channel + defense-specific",
    REDF, RED, 9.2, "bold", RED)

# ---- defense placement banners ----
box(2, 6.5, 60, 6.5,
    "IN SCOPE — transmitter-blocking (comprehensive):  STT · SPT · Recon · NDA · fence/delay\n"
    "security def = \"no transmitter executes on protected data in the window\"  →  SAME def as our oracle",
    GREENF, GREEN, 8.8, "bold", GREEN)
box(66, 0.5, 61, 5.2,
    "OUT OF SCOPE — footprint-hiding:  InvisiSpec · CleanupSpec · SpecLFB · MuonTrap\n"
    "let the transmitter FIRE, hide/undo the footprint  →  bug lives in the channel, not the transmitter",
    REDF, RED, 8.8, "bold", RED)

fig.tight_layout()
fig.savefig("/tests/simspect/docs/scope_diagram.png", dpi=150, bbox_inches="tight")
print("wrote docs/scope_diagram.png")
