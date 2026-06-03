# bug/graphs — hit attribution, by testset × implementation × category

Regenerate: `python3 bug/graphs/make_graphs.py` (matplotlib; numbers are baked in with provenance
comments, verified from `results/<run>/diagnostics/buckets/` + `window-results.json` + `claudelog.md`).

A SimSpect **hit** = gem5 permits what the Alloy model forbids. These charts answer the only question
that matters about a hit: **which layer did it actually come from** — a real **TARGET** defense bug
(the signal), a **CHECKER** measurement artifact, an **ALLOY** model/concretization artifact, or a
**PIPELINE/CONFIG** defect. Colors are consistent across all three (see `../BUG_TAXONOMY.md`):
🔴 target · 🟠 checker · 🔵 alloy · 🟡 pipeline · ⚪ config · 🟢 clean (0 hits) · ⚫ open/unattributed.

| file | what it shows |
|---|---|
| `hit_attribution_by_category.png` | one panel **per (testset × implementation)** run: every hit-bucket as a log-scaled bar, colored by category. The drill-down. |
| `coverage_matrix.png` | the testset × implementation grid: which combos ran and the **dominant** hit category per cell (blank = not run / unusable). |
| `findings_by_category.png` | the catalogued findings (A*/B*/C*/D*) counted by layer — regime-independent summary. |

## Headline (what the charts say)

- **Exactly one hit, across every run, is a confirmed real target leak from generator output:** Recon_6
  `inst-014912` (SLF / store-to-load-forward taint bypass, **A2**). Everything else on the recon STT
  builds is the **B1** `check_ld` false positive (183/184).
- **The Alloy model is the dominant source of *false* signal.** On SPT-Fence the ld "hits" are ~100%
  **alloy** over-approximation (const-addr **C2**) + concretization clobber (**C1**) — 6,118 (stock) /
  ~48k (slow-comm), **0 real leaks**.
- **The real timing-race signal only appears under slow-comm:** 186 STT VP↔squash-race hits (**A4**, full
  attribution) and 983 SPT-Fence candidates (**A5**, attribution open) — `commitToIEWDelay≥3`, **0 at
  stock**.
- **Stock STT (`/work/stt`) holds:** 0 hits on STT_6 / interleave (the prior br_x "leaks" were the **B2**
  checker bug, now fixed).
- **`STT_all`×Amulet is not usable as-is:** pre-`check_br`-fix + un-typed → unattributable (grey); earlier
  it was 100% errors from the `caches:true` port bug (**D4**). Re-run with fixed checkers before trusting.

⚠️ Counts marked *PARTIAL* (recon-modded STT_6/interleave) or *SAMPLE* (STT slow-comm 600/mode) are not
full-corpus. The Amulet bar is **un-attributed**. See each panel's caption.
