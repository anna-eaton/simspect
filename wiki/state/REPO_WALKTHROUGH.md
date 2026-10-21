# REPO WALKTHROUGH — every corner, ticked off as understood

*Built 2026-10-20 (cleanuprepo session). Purpose: Anna walks the WHOLE repo with Claude, section by
section, until she understands every file. Check a box `[x]` only once she confirms she gets it.
⚠️ = flagged cleanup candidate (junk / stale / mis-tracked) — decide as we go.*

**Legend:** `[ ]` not yet walked · `[x]` understood · ⚠️ cleanup candidate · `?` purpose unclear, clarify

**Progress:** 0 / 15 sections

---

## 1. Core pipeline — root orchestrators `[ ]`
The engine + the producer/consumer that drive the 4 stages. (`pipeline.py` is the reused engine;
the others are thin orchestrators on top.)
- [ ] `pipeline.py` — the 4-phase engine (xml→llvm→asm→gem5), config→env bridge, streaming
- [ ] `testsetgen.py` — PRODUCER: runs xml in bg while llvm+asm drain each instance (make gen)
- [ ] `testrun.py` — CONSUMER: per-kind results partitioning + timestamped campaigns (make run)
- [ ] `sweep_monitor.py` — sweep status monitor (used by dashboard + CLI)
- [ ] `simspect_paths.py` — single source of truth for repo paths (`ROOT`, TESTSETS, …)
- [ ] `jobs_registry.py` — the jobs registry (producer/consumer/dashboard read it)
- [ ] `Makefile` — wraps everything (hold/cafe/status/dash/gen/run/pipeline/all/xml/llvm/asm)
- [ ] ⚠️ `categorize_hits.py` — old hit categorizer (May 28, pre-diagnostics) — likely superseded
- [ ] ⚠️ `poc_edit_lsq.py` — 899B scratch snippet `?`

## 2. STAGE 1 — Alloy models + enumeration `[ ]`
`STAGE1_alloy/` — the symbolic model (semantic ground truth, PROTECTED) + the instance enumerators.
- [ ] `models/*.als` — the CURRENT models: `STT_6`, `SPT_6`, `SPT_6_oneLP`(+`_noSTLF`), `Recon_6`,
      `STT_6_core`, `STT_6_multisource`, `STT_6_pincommit`, `STT_6_modified_protset`, `SPT_6_full`
      (symlink), `STT_6_interleave`/`STT_all` (symlinks→STT_6), older `STT_2..5`, `LP-only-STT_3`
- [ ] `models/old_models/*.als` (24 files) — ⚠️ archived earlier model generations
- [ ] `models/util/{ordering,myordering}.als`, `models/execution-theme.thm` — Alloy support files
- [ ] `a6CountModels.java`/`.class`, `a6CountOnly.java`/`.class`, `a6DiverseModels.java`,
      `alloy6.jar` — the Alloy-6 instance enumerators (Java)
- [ ] `stage_seed.py`, `stage_pipeline.py` — June staged-enumeration tooling (minimal-core→fleshout)
- [ ] `visualizer/visualize.py` — instance visualizer
- [ ] ⚠️ `dummy_out/` (28 files), `results.json`, `__pycache__/` — generated/scratch outputs

## 3. STAGE 2 — concretization (XML → LLVM → asm) `[ ]`
`STAGE2_compilation/` — turns Alloy XML into real x86 litmus programs.
- [ ] `parsexml.py` — THE concretization (all passes: state→instr→branches→operands→SSA→LLVM); PROTECTED-spirit
- [ ] `compile_annotate.py` — compiles .ll → .s + resolves annotations
- [ ] `batch_generate.py` — runs the pipeline over a folder of XML
- [ ] `find_duplicates.py` — canonicalize + dedupe instances
- [ ] `instruction_tables/instructions.jsonc` — the instruction table (ld/str/br/other mappings)
- [ ] `SimSpect Concretization Passes.md`, `simspectmaster.md` — stage docs
- [ ] ⚠️ `m5out/stats.txt`, `__pycache__/` — stray gem5 output / bytecode

## 4. STAGE 3 — gem5 checkers (the leak oracle) `[ ]`
`STAGE3_gem5/` — runs each program on gem5 and decides leak / no-leak per transmitter kind.
- [ ] `check_ld.py` — load-transmitter checker (the data-obtained gate; canonical)
- [ ] `check_br.py` — branch-redirect checker (known-weak; the standing rewrite item)
- [ ] `check_other.py` — other/ALU transmitter checker
- [ ] `gem5_common.py` — shared gem5 invocation (reads SIMSPECT_* env)
- [ ] `check_ld_speclfb.py`, `check_ld_invisispec.py`, `check_ld_invisispec_compound.py`,
      `check_ld_cleanupspec.py` — AMuLeT per-defense load checkers
- [ ] `check_ld_timing.py` — timing-detail variant
- [ ] `diag_ld_cache_reach.py` — cache-reach diagnostic helper
- [ ] ⚠️ `old_scripts/` (4), `jsons/` (2), `results-scheme0.json`, `results-scheme2.json`,
      `results.json`, `__pycache__/` — stale scripts / scratch outputs

## 5. Run configs `[ ]`
`runconfigs/` — one JSONC per build/scheme (the reproducibility provenance).
- [ ] STT: `run_config_STT_6.jsonc` (+`_j12`, `_takenonly`, `_interleave`×3), `STT_5`, `STT_all`
- [ ] SPT: `SPT_6`, `SPT_6_oneLP`, `_full`, `_disableUntaint`, `_FuturisticFence`,
      `_FuturisticInvisibleSpec`, `_SpectreInvisibleSpec`
- [ ] OTB/misc: `otb_probe`, `otb_search_c1/c2`, `smoke`, `verify_ld_taken`

## 6. Dashboard `[ ]`
`dashboard/` — stdlib web console (make dash). Moved here this session; shared modules stayed at root.
- [ ] `dashboard.py` — HTTP server + routes + markdown renderer + vscode links
- [ ] `dashboard_data.py` — all data functions (overview/corpora/checkers/execgraph/vscode_uri)
- [ ] `dashboard_ui.py` — the single-page HTML/CSS/JS (PAGE)

## 7. Infra / rig `[ ]`
`scripts/` — connect-or-create Slurm→docker→tmux→dashboard rig.
- [ ] `scripts/sim` — the rig driver (hold/cafe/status/dash/peek/windows/mini/…)
- [ ] `scripts/simspect.env` — host/container/tmux config vars

## 8. gem5-hooks (new this session) `[ ]`
`gem5-hooks/` — durable backup of the gem5 instrumentation (lived only in the container before).
- [ ] `README.md` — base commits + recon=base/modded=change + re-apply/re-capture
- [ ] `stt/`, `stt-dbg/`, `gem5-spt/` — `.patch` + `se_exp.py`/`se_slowcomm.py`
- [ ] `gem5-recon-modded/recon-modded_{src,configs}.diff` — the BTB-override Recon hooks
- [ ] `amulet-repo/{analyze_gadgets,gen_stt_tests}.py` — amulet gen scripts

## 9. Wiki — state `[ ]`
`wiki/state/` — always-current living docs.
- [ ] `INFRA.md` — the connect/run runbook (+ deploy-key auth, dashboard)
- [ ] `COMMANDS.md` — command reference `?` (verify contents)
- [ ] `REPO_MAP.md` — the file inventory (this session)
- [ ] `SYNC_DIVERGENCE.md` — Mac↔cafe2 reconciliation + gem5-hook durability
- [ ] `REPO_WALKTHROUGH.md` — THIS file
- [ ] `README.md` (wiki root) + `REPO_CLEANUP_BRIEF.md` — the index + the brief

## 10. Wiki — design `[ ]`
`wiki/design/` — durable semantics/methods (migrated this session).
- [ ] `DESIGN.md` — the speculation contract + cross-stage invariants (read before touching .als)
- [ ] `AUDIT.md` — known issues/findings audit
- [ ] `METHODS_{CONCRETIZATION,INSTRUMENTATION,LEAKAGE_KNOBS}.md` — methodology docs
- [ ] `branch_enumeration_notes.md`, `sweep_design_notes.md` — design drafts
- [ ] `docs/` — `AMULET_VS_SIMSPECT_SCOPE.md`, `COMPOUND_TRANSMISSION_CRITERION.md`,
      `make_scope_diagram.py` + `scope_diagram.png`

## 11. Wiki — findings `[ ]`
`wiki/findings/` — per-bug / per-result writeups (migrated this session).
- [ ] `bug/BUG_TAXONOMY.md`, `bug/BUGS.md` — the bug catalog (A*/B*/C*/D* ids)
- [ ] `bug/stt_slowcomm_vp_squash_race/` — the STT VP-squash race bug (explainer + diag + example + inst)
- [ ] `bug/recon_SLF_stlf_bypass/` — the Recon STL/SLF bypass bug (note + provenance + inst-014912)
- [ ] `bug/graphs/` — make_graphs.py + 3 PNGs (findings-by-category etc.)
- [ ] `bug/{kv1,kv3,uv2}_demo/`, `bug/STT_KV3_TLB_REVIEW.md` — June PoC demos (KV1/KV3/UV2)
- [ ] `mdsToRead/` (10 docs) — key analyses: OTB_GENERATION_GAP, ALLOY_RF_LASTWRITER_BUG,
      STT_BRANCH_LEAK_ROOTCAUSE, SPT_FENCE_NO_HOLD, POTENTIAL_MODEL_FIX_constaddr, + 5 June AMuLeT/enum docs

## 12. Wiki — results + root logs `[ ]`
- [ ] `wiki/results/` — `results.md`, `reconresults.md`, `PAPER_RESULTS.md`, `PAPER_EXPERIMENTS.md`, `EXPERIMENTS.md`
- [ ] root `STATUS.md` — human rollup (stays at root; dashboard reads it)
- [ ] root `claudelog.md` — durable append-only findings log (stays at root)
- [ ] root `claudenotes.md` — ephemeral right-now scratchpad (stays at root)
- [ ] root `CLAUDE.md` — project directives (stays at root)

## 13. bugsynth — the June bug-synthesis workspace `[ ]`
`bugsynth/` (60 files) — a self-contained copy of the pipeline used to hand-synthesize & reproduce
specific bugs (nmosier pending-squash, OTB getOldestTaint, channel-D, branch-NI). `?` Decide: keep as-is,
or is it a snapshot that should be thinned?
- [ ] Design/review docs (9 `.md`): NMOSIER_PENDING_SQUASH_BUG, OTB_BUG_REVIEW, PENDING_SQUASH_*,
      CHANNEL_D_DESIGN, BRANCH_CHANNEL_CHECK_DESIGN, CHECK_BR_NI, RECON_OLDEST_TAINT_BUG, FINDINGS_SUMMARY, WALKTHROUGH
- [ ] Checkers/probes: `check_br_differential.py`, `check_br_ni.py`, `br_ni_audit.py`,
      `otb_check.py`, `otb_merge_check.py`, `pendsquash_diff.py`, `stt_branch_soundness_audit.py`, `channel_d/`
- [ ] `models/` (5 .als: STT_6 + otb/otb2/alupath/pendsquash variants) — ⚠️ bugsynth-local .als copies
- [ ] `configs/` (8 otb/pendsquash run configs), `pipeline.py` — ⚠️ duplicated pipeline + configs
- [ ] ⚠️ nested `STAGE2_compilation/` + `STAGE3_gem5/` — full duplicate stage snapshots

## 14. Paper figures + plots `[ ]`
- [ ] `paper_figures/` — `make_paper_figures.py` + 21 F*.png + `figures.tex` + `README.md` +
      `YARCH_PORT_PLAN.md` + `reviews/` (4 reviewer md). Note: paper itself is a SEPARATE repo.
- [ ] ⚠️ `plots/` (26) — generated analysis PNGs + `hit_categories.py` (likely regenerable)

## 15. Legacy / scratch / junk — CLEANUP CANDIDATES `[ ]`
Walk these to decide delete/archive/gitignore.
- [ ] ⚠️ `analysis/` — **3,281 tracked files** of hit dumps → should be gitignored, not in git
- [ ] ⚠️ `old/` (13) — alloy4.2.jar, CountModels*, old parsexml/run_panel/xml2*, RECAP.md, `.inetloc`
- [ ] ⚠️ `old_scripts/` (11) — analyze_*/investigate_*/verify_* scripts (superseded)
- [ ] ⚠️ `oldest_taint_bug/` (23) — patched parsexml + debug_out dump (old investigation)
- [ ] ⚠️ `target-bug/` (6), `STL_bug/` (5) — one-off bug scratch dirs
- [ ] ⚠️ `latestmodels/` (17) — .als copies + gen logs + run_configs (duplicate of STAGE1 + logs)
- [ ] ⚠️ `__pycache__/` (root, 4) + scattered `__pycache__/` + `*.pyc`/`*.class` — bytecode, should be gitignored
- [ ] ⚠️ `m5out/stats.txt` (root) — stray gem5 scratch output
- [ ] ⚠️ root **log files**: `launch_*.log`, `pipeline_*.log` (×6), `testrun_*.log` (×2),
      `queue_recon_behind.log`, `poc_gem5_build.log` — run logs, should not be tracked
- [ ] ⚠️ root **latex build junk**: `paper.aux`, `paper.log`, `paper.out`, `texput.log` (paper is elsewhere!)
- [ ] ⚠️ root **PDFs**: `amulet.pdf`, `InvisiSpec_*.pdf`, `sec24summer-*.pdf` — reference papers (keep? move?)
- [ ] ⚠️ root **misc**: `Screenshot 2026-06-06*.png`, `run_config.jsonc` (stray), `poc_build.sh`,
      `queue_recon_behind.sh`, `recon_author_email.txt`
- [ ] `LICENSE`, `.gitignore` — keep (housekeeping)

---

## Running cleanup decisions (fill in as we walk)
| item | decision | done |
|------|----------|------|
| | | |
