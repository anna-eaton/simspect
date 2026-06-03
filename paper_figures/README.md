# paper_figures — candidate figures for the SimSpect results writeup

**`figures.tex`** — standalone **TikZ / pgfplots / booktabs** source for the paper (the big bug table +
F2/F1c tables + F3/F4/F5/F8 charts + F6/F7 schematics as native TikZ). `pdflatex figures.tex` (needs
`tikz`, `pgfplots`≥1.16, `booktabs`). Written without a local TeX install → unverified locally, standard
constructs only. The PNGs below are the raster preview / candidate set.

Regenerate PNGs: `python3 paper_figures/make_paper_figures.py` (matplotlib; every number is **baked in
with a provenance comment** in the script header — same discipline as `bug/graphs/make_graphs.py`,
verified from `results/<run>/diagnostics/buckets/`, `results/experiments/.../summary.json`,
`/work/amulet-repo/stt_corpus_gadgets.json`, and dated `claudelog.md` entries).

Narrative + per-figure interpretation: [`../PAPER_RESULTS.md`](../PAPER_RESULTS.md). Each slot has
**three candidate renderings** (`_a`/`_b`/`_c`) — pick one per slot.

| slot | candidates | what it shows |
|---|---|---|
| **F1** hit attribution | `F1_attribution_{a,b,c}.png` | per (testset×defense): raw hits → real bug, colored by layer. **a** = log bars · **b** = disqualifier funnel · **c** = scoreboard table |
| **F2** AMuLeT scope | `F2_scope_{a,b,c}.png` | the 8 AMuLeT bugs vs SimSpect's leakage model (1 in scope: UV6). **a** = IN/OUT matrix · **b** = by channel · **c** = 2×2 quadrant |
| **F3** test targeting | `F3_targeting_{a,b,c}.png` | only 17% of AMuLeT's tests can leak vs 100% of SimSpect's. **a** = stacked bars · **b** = gadget breakdown · **c** = yield donuts |
| **F4** stall sensitivity | `F4_stalls_{a,b,c}.png` | s_U masks, s_R flat, fnc plateaus (STT @ commitToIEWDelay=3, 100% race-bucketed). **a** = 3 panels · **b** = normalized overlay · **c** = tornado |
| **F5** fragility | `F5_fragility_{a,b,c}.png` | leak count vs commitToIEWDelay. **a** = STT curve · **b** = STT vs Fence raw-vs-filtered · **c** = fragility ranking |
| **F6** VP↔squash race | `F6_vp_squash_race.png` | the timeline + the shared bad logic (STT A4 == SPT A5) |
| **F7** recon bugs | `F7_recon_bugs.png` | OTB (`getOldestTaint`) + STL/SLF gadget schematics |
| **F8** AMuLeT efficiency | `F8_efficiency_{a,b,c}.png` | MEASURED on the SpecLFB build (UV6): SimSpect #6/23% vs AMuLeT #39/3.3% detection (6.5× targeting); **gem5 sim cost comparable** (0.092 vs 0.057 s/test). **a** = 3-panel · **b** = per-test cost decomposition (only gem5-sim is comparable; rest = pipeview+boot instrumentation) · **c** = AMuLeT profile + targeting |
| **F9** bug table | `F9_bug_table.png` (+ `figures.tex` Tab.1) | **the big table grouped by defense**: every bug, where first known, found by SimSpect/AMuLeT/both, scope, verdict |

⚠️ Counts marked SAMPLE (slow-comm 300–600/mode) or candidate/open are not full-corpus settled
numbers; see the per-figure captions and `PAPER_RESULTS.md` §9 (limitations). Colors match
`bug/BUG_TAXONOMY.md`: 🔴 target · 🟠 checker · 🔵 alloy · 🟡 pipeline · ⚪ config · 🟢 holds.
