# REPO_MAP — inventory & status audit

*Built by the cleanup-agent session, 2026-10-20. Status column is a **proposal/guess** — nothing
is moved or deleted. Walk through with Anna; record decisions in `wiki/logs/claudelog.md`.*

Skips generated/large dirs: `testsets/`, `results/`, `generated/`, `.git/`, `__pycache__/`,
`analysis/` (3281 files, hit dumps), `m5out/`.

## Root markdown (17 files) — the main consolidation target

| File | mtime | tracked | what it is | status guess → wiki dest |
|------|-------|---------|-----------|--------------------------|
| `CLAUDE.md` | 10-20 | ✓ | project directives | **current — stays at root** (tool-read) |
| `claudelog.md` (164K) | 10-20 | ✓ | append-only findings log | current — **root** (referenced by dashboard, watchers) → symlink/copy into `wiki/logs/` |
| `claudenotes.md` (37K) | 10-13 | ✓ | ephemeral scratchpad | current — **root** (same ref concern) → `wiki/logs/` |
| `STATUS.md` | 10-13 | ✓ | human rollup for Anna | current — **root** (dashboard `CODE_ROOT/STATUS.md`, line 42) → mirror to `wiki/state/` |
| `DESIGN.md` (3.6K) | 05-28 | ✓ | durable semantics/contract | current → `wiki/design/` |
| `AUDIT.md` | 10-13 | ✓ | known issues/findings audit | current → `wiki/design/` |
| `METHODS_CONCRETIZATION.md` | 10-13 | ✓ | methods doc | current → `wiki/design/` |
| `METHODS_INSTRUMENTATION.md` | 10-13 | ✓ | methods doc | current → `wiki/design/` |
| `METHODS_LEAKAGE_KNOBS.md` | 10-13 | ✓ | methods doc | current → `wiki/design/` |
| `branch_enumeration_notes.md` | 10-13 | ✓ | draft: pass2_5 branch enum | design draft → `wiki/design/` |
| `sweep_design_notes.md` | 10-13 | ✓ | 06-01 design consult (inspection only) | stale-ish design → `wiki/design/` |
| `results.md` | 10-13 | ✓ | run writeups | current → `wiki/findings/` or `wiki/results/` (decide) |
| `reconresults.md` | 10-13 | ✓ | recon run writeups | current → `wiki/findings/`/`results/` |
| `PAPER_RESULTS.md` (43K) | 10-13 | ✓ | paper results | current → `wiki/findings/`/`results/` |
| `EXPERIMENTS.md` | 10-13 | ✓ | 06-02 experiment plan | possibly stale → `wiki/findings/` or archive |
| `PAPER_EXPERIMENTS.md` | 10-13 | ✓ | methods justification | current → `wiki/design/` or `results/` |
| `RECAP.md` | 10-13 | ✓ | 06-03 recap compiled from logs | **superseded by logs/STATUS** → archive? |

## Root python (11 files)

| File | mtime | tracked | what it is | status guess |
|------|-------|---------|-----------|--------------|
| `pipeline.py` (51K) | 10-13 | ✓ | the pipeline engine | **current — core** |
| `testsetgen.py` | 10-13 | ✓ | producer orchestrator | current |
| `testrun.py` | 10-13 | ✓ | consumer orchestrator | current |
| `dashboard.py` | 10-13 | ✓ | dashboard entry | **current** (Oct dashboard set) |
| `dashboard_data.py` (38K) | 10-13 | ✗ untracked | dashboard backend | current — **needs commit** |
| `dashboard_ui.py` (39K) | 10-13 | ✗ untracked | dashboard UI | current — **needs commit** |
| `jobs_registry.py` | 10-13 | ✗ untracked | dashboard jobs registry | current — **needs commit** |
| `simspect_paths.py` | 10-13 | ✗ untracked | shared path helper (`P.ROOT`) | current — **needs commit** |
| `sweep_monitor.py` (37K) | 10-13 | ✓ | sweep monitor | current |
| `categorize_hits.py` | 05-28 | ✓ | old hit categorizer | stale? superseded by diagnostics/ |
| `poc_edit_lsq.py` | 10-13 | ✓ | 899B poc snippet | unknown — likely scratch |

## Directories

| Dir | files/size | what it is | status guess |
|-----|-----------|-----------|--------------|
| `STAGE1_alloy/` | — | Alloy models (**PROTECTED**) | current — do not touch |
| `STAGE2_compilation/` | — | parsexml etc | current |
| `STAGE3_gem5/` | — | checkers | current |
| `runconfigs/` | — | run configs | current |
| `scripts/` | sim, simspect.env (untracked) | the connect/create rig | current — **needs commit** |
| `wiki/` | README, INFRA, brief | new taxonomy scaffold | current — target |
| `bug/` | 20 / 104K | BUG_TAXONOMY, BUGS, per-bug trees | current findings → `wiki/findings/` |
| `mdsToRead/` | 5 / 68K | key analysis md (OTB gap etc) | current findings → `wiki/findings/` |
| `docs/` | 2 / 32K | AMULET scope, compound criterion | current → `wiki/design/` |
| `paper_figures/` | 30 / 88K | figures + make_paper_figures.py | current (paper) — keep |
| `plots/` | 26 / 4K | generated plots + hit_categories.py | mostly generated → gitignore? |
| `latestmodels/` | 17 / 4K | .als copies + gen logs + run_configs | **duplicate .als copies** — verify vs STAGE1 |
| `analysis/` | 3281 | hit dumps per model | generated — gitignore |
| `m5out/` | 1 | gem5 stats.txt stray | **dead** — gem5 scratch output |
| `old/` | 15212 / 112K | alloy4.2.jar, old parsexml, run_panel | **likely dead** — quarantine confirmed |
| `old_scripts/` | 11 / 104K | analyze_*/investigate_* scripts | **likely dead/superseded** |
| `oldest_taint_bug/` | 23 / 92K | patched parsexml + debug_out | stale bug investigation → archive? |
| `STL_bug/` | 5 | store-addr bug .s files | findings → `wiki/findings/` or archive |
| `target-bug/` | 6 | alloy-out dump | stale bug investigation? |
| `latestmodels/`, `STL_bug/`, `target-bug/`, `oldest_taint_bug/` | | scattered bug/model dirs | consolidate under findings or archive |

## Protected / caution

- **`STAGE1_alloy/models/*.als`** — per CLAUDE.md, no edit/move/rename without per-file sign-off.
  - ⚠ Untracked stray: `STAGE1_alloy/models/SPT_6_oneLP 2.als` — looks like a Finder dup-copy
    (" 2" suffix). Needs Anna's call (protected file; confirm it's a duplicate before anything).
- **Reference coupling** (move = break): `dashboard.py` reads `CODE_ROOT/STATUS.md` (line 42) and
  follows its md links; `bug/graphs/make_graphs.py` references `claudelog.md`. These must move
  together with their targets or stay at root.

## Mac ↔ cafe2 divergence (brief's blocking item)

Not yet reconciled — requires `make cafe` into the container. Brief flags untracked June work on
cafe2 (incl. protected `.als`: `STT_6_core.als`, `STT_6_multisource.als`). **Open — awaiting Anna's
go to connect and diff.** (Note: brief's "last real work 2026-06-10" line looks stale; logs updated
through 10-20.)
