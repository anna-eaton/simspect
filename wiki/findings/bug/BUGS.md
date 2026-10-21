# SimSpect bug catalog (cross-build)

Master index of issues found across every gem5 build + the pipeline. Each entry gives the
**signature**, the **verdict** (real gem5/defense bug vs. pipeline-artifact vs. checker vs. codegen
vs. model-expressivity vs. config/testset), the **provenance** (which run/commit it was seen on),
and **status**. Representative example folders live next to this file; everything else is
cross-referenced to its `claudelog.md` entry / `results/<run>/diagnostics/` + bug `.md` so this stays
a thin index and isn't duplicated.

> **Two views of the same findings:** this file is organized **by gem5 build**.
> [`BUG_TAXONOMY.md`](BUG_TAXONOMY.md) is the same findings organized **by root-cause layer**
> (target / checker / alloy / pipeline) — the triage drill-down + summary matrix.
> [`graphs/`](graphs/) holds per-(testset × implementation) hit-attribution charts colored by category
> (`python3 graphs/make_graphs.py` regenerates them).

Legend — verdict: 🔴 real gem5/defense bug · 🟠 checker artifact · 🟡 pipeline/codegen/concretization
· 🔵 model-expressivity/enumeration · ⚪ config/testset realizability (not a bug).
Status: ✅ verified · 🛠 fixed · ⏳ open/pending owner.

---

## /work/gem5-recon-modded  — STT (scheme 2), incl. Recon `allow_leaked`

### 🔴✅ recon_SLF_stlf_bypass — store-to-load forwarding bypasses STT taint check
- **Signature:** a tainted *speculative* load whose address comes from a speculative source, with a
  prior store to the same address; the LSQ forwards the store data and the load is marked **ready
  within ROB** (completes) inside the speculative window, *before* its squash — no cache packet.
- **Verdict:** REAL defense bug. **Representative:** `bug/recon_SLF_stlf_bypass/` (`inst-014912`).
- **Provenance:** `results/Recon_6__20260602_122016` mispredict_not_taken/ld; build mtime 2026-05-21;
  repo `d8b6caa-dirty`. 1 of 184 ld hits is real; see `claudelog` 2026-06-02 19:22 (VERDICT 20:40).
- **Correct leak criterion:** *data obtained (completes) before squash*, NOT cache-reach — a cache
  packet test misses SLF. Now in `check_ld` as the `store_forward`/data-obtained gate.

### 🔵✅ recon "OTB" classifier matches are NOT real OTB
- **Signature:** `diag_recon_load_hits.py` flags `inst-004271/4272/4273` as OTB (`getOldestTaint`),
  but in the concretized asm the spec load overwrites `%rax` and the TOther (`idivq`) output is dead
  → xmit address fed by a *single* spec load, not a committed+spec merge.
- **Verdict:** classifier false match (abstract **shared opstate ≠ rf edge**). Real OTB shape is
  generatable only with a forcing predicate. See `mdsToRead/OTB_GENERATION_GAP.md`,
  `claudelog` 19:22, and `results/Recon_6__20260602_122016/diagnostics/`.

---

## /work/stt — STT build

### 🟠🛠 check_ld false positive — scores at "Executing load", not completion
- **Signature:** check_ld counted a load as leaking at the LSQ "Executing load" tick, but a tainted
  load bounced to `delay_unit` (`lsq_unit.cc:2104`) and squashed *without completing* never leaked.
  Inflated recon/STT ld hit counts (183/184 of the Recon_6 ld hits were this).
- **Verdict:** checker artifact. **Status:** FIXED — `check_ld` now ANDs a data-obtained gate
  (reached_cache OR store_forward); delay_unit bounce / spec_read_only / never_executed are dropped.
  See `claudelog` 2026-06-02 22:45.

### 🟠🛠 check_br false positive — keyed on complete tick, not squash tick
- **Signature:** STT br_x "hits" were check_br false positives; STT branch defense holds (made-pending
  under sweep stall). **Verdict:** checker artifact, FIXED to key on squash tick.
- **Provenance:** `claudelog` 2026-06-02 00:30; [[project_stt_branch_leak_cause]].

### 🔴⏳ STT visibility-point ↔ squash race (slow-comm regime only)
- **Signature:** when the controlling mispredict resolves, STT clears the producer load's taint
  (`isPrevBrsResolved`) → the wrong-path xmit load un-taints and accesses cache in the gap *before*
  the squash flushes it from the LSQ. Real cache packet (`reached_cache`), then squashed. Driver is
  `commitToIEWDelay` (≳ 2–3); does NOT leak at stock timing; not squashWidth. fnc-hook / check_ld-FP /
  model-over-approx all ruled out.
- **Verdict:** real STT design-level race, only exposed under the slow-comm experiment timing.
- **Representative:** `bug/stt_slowcomm_vp_squash_race/` (`inst-047231`) — full provenance.json,
  BUG_EXPLAINER.md, example writeup, diagnostic, asm/ann/xml.
- **Provenance:** `results/experiments/slow_comm_squash1`; `claudelog` 2026-06-02 09:30.
  *(found by designconsultant; copied here, not independently re-verified this session.)*

### 🟡🛠 gem5 O3 livelock at commitToIEWDelay ≥ 5
- **Signature:** generic gem5 livelock (NOT STT/NOT a hook) when `commitToIEWDelay ≥ 5`; capped at 4.
- **Verdict:** generic gem5 timing artifact. **Provenance:** `claudelog` 2026-06-02 04:30.

---

## /work/gem5-spt — SPT build (DerivO3CPU)

### ⚪✅ SPT "Fence leaks pre-squash" — zero-init prologue untaint (NOT a bug)
- **Signature:** Fence showed pre-squash speculative cache accesses at both slow-comm AND stock
  timing. Root-caused to the zero-init prologue untainting all shadowL1 → no live taint source →
  testset realizability gap. **Verdict:** testset/config artifact, not a defense bug.
- **Provenance:** [[project_spt_onelp_zeroinit_untaint]]; `claudelog` 2026-06-02 18:50.
  *(per runManager/hit-inspector; not independently re-verified here.)*

### ⚪/🔵⏳ SPT OtherLoad hits — STLF-untaint from untainted-constant stores
- **Signature:** SPT_6_full 43 OtherLoad hits explained by store-to-load-forward untaint from
  untainted constant stores; over-approximation, not real leaks (15 STLF check_ld-FP + 19 safe-load
  over-approx of 34 in oneLP_fence). **Verdict:** mostly testset over-approximation / checker FP.
- **Provenance:** [[project_spt_load_diagnosis]]; `results/SPT_6_oneLP_fence__20260602_013615/diagnostics/`;
  `claudelog` 2026-06-02 09:00 / 02:40.

---

## /work/amulet — amulet defenses

- Hooks built (BTB-force + branch-resolve-stall ported); **no sweep results yet** → no bugs catalogued.
  See [[project_amulet_hooks]].

---

## Pipeline / Stage-2 / model / tooling (build-agnostic)

### 🟡🛠 dup-PC codegen bug (parsexml Stage 2)
- **Signature:** xm-branch NOP injection duplicates a PC label when the xmit branch is followed by
  another branch → `symbol already defined` → ~6% of br_x tests fail compile + dropped (e.g.
  `inst-017570`, `inst-014962`, `inst-020383`). **Verdict:** Stage-2 codegen bug, FIXED
  (opus-claude 22:50); relaunch from parsexml. **Provenance:** [[project_dup_pc_bug]].

### 🟡⏳ Alloy rf last-writer / register-state collision (concretization)
- **Signature:** rf not pinned to most-recent writer → register-state collision → ~58% of testset
  has unrealizable dataflow (concretization may wire an address to the public producer). Explains
  several SPT load→load reached_cache and the recon "OTB" false matches. **Verdict:** concretization
  bug; fix = Option A across 17 models + regen all; NOT applied (owner gate).
  **Provenance:** [[project_alloy_rf_lastwriter_bug]]; `mdsToRead/ALLOY_RF_LASTWRITER_BUG.md`.

### 🔵⏳ OTB generation gap (enumeration cap, not a model limit)
- **Signature:** the OTB precursor `ld→other→xm` is absent from the default 100k enumeration (every
  ld xmit address is fed directly from a single load) but is LEGAL (SAT when forced with an
  `otb_shape` predicate) — a `max_instances` cap/ordering artifact. **Verdict:** enumeration gap,
  needs a forcing predicate (model/config change → owner approval).
  **Provenance:** `mdsToRead/OTB_GENERATION_GAP.md`; [[project_otb_generation_gap]].

### 🟡🛠 pipeview space blowup (gem5 launch unbounded)
- **Signature:** unbounded O3PipeView from runaway/livelocked gem5 (no subprocess timeout) +
  orphaned gem5 holding deleted inodes → disk-full crashes. **Verdict:** tooling bug, FIXED
  (timeout + orphan-proof pdeathsig + tick cap). **Provenance:** [[project_pipeview_space_blowup]];
  `claudelog` 2026-06-02 (6:spaceAudit).

### 🟠🛠 diag_ld_cache_reach faithful-repro bug (sweep stalls dropped)
- **Signature:** the cache-reach diag reran gem5 with the RAW annotation, omitting the sweep's
  `unresolved_stall_cycles` (lives in `sweep.*`, injected into the ann by `pipeline._inject_stalls`,
  not an env var) → speculative window collapsed → invalid rerun. **Verdict:** diagnostic bug, FIXED
  (forwards `sweep.*` as `SIMSPECT_SWEEP_CFG`, rebuilds the grid + injects stalls per point).
  **Provenance:** `claudelog` 2026-06-02 19:22; [[reference_check_ld_cache_reach_diag]].

---

## Verification status of this catalog

- **Independently verified in this session (4a:reconHitDiag):** recon SLF leak, recon "OTB"
  non-realization, check_ld over-count mechanism, diag_ld_cache_reach repro bug.
- **Cross-referenced from other sessions' claudelog/diagnostics (not re-verified here):** STT VP↔squash
  race, commitToIEWDelay livelock, SPT zero-init untaint, SPT OtherLoad STLF, dup-PC, Alloy rf
  last-writer, OTB generation gap, pipeview blowup. Each carries its own bug `.md` + provenance at the
  cited location; re-verify with a faithful (stall-injected) rerun before treating as settled.
