# BRIEF — repo status audit & layout cleanup (for the cleanup agent)

**You are a fresh agent started in this repo. Read this top-to-bottom, then read the root
`CLAUDE.md` in full. Your job: walk the whole repo *with Anna*, classify what's old / new / dead /
duplicated, and consolidate the layout — especially the ~40 scattered markdown files — into the
`wiki/` taxonomy, WITHOUT breaking anything or touching protected files.**

This is an interactive, file-by-file walkthrough. Anna wants to talk through it with you. You
propose; she decides. You do not bulk-move or delete on your own.

## Hard rules (non-negotiable — from CLAUDE.md)

1. **Never edit, move, rename, or regenerate any `.als` / anything under `STAGE1_alloy/models/`**
   without Anna's explicit per-file sign-off. The models are the semantic ground truth. Reading is
   fine; proposing a diff is fine; applying is approval-only.
2. **Never mutate git** (commit/add/mv/rm/push/pull/checkout/restore/clean/reset) unless Anna
   explicitly asks for that specific action in the current message. A "cleanup" is **not** blanket
   approval to `git mv`/`git rm`. Default to proposing; let her run the git.
3. **Don't tune the pipeline / `parsexml.py` / gem5 hooks** to hit or avoid bug cases. Only fix
   things that are actually wrong, and flag anything semantics-affecting for approval.
4. **Conservative always.** If unsure whether a file is dead, leave it and ask. Never delete
   something you didn't create or can't prove is dead.

## Do this FIRST: reconcile the Mac ↔ cafe2 divergence (blocking)

Code source of truth is **local (this Mac)**; cafe2 pulls via git. **But the two have diverged and
neither is committed.** The cafe2 container (`gem5_dev:/tests/simspect`, reach it via `make cafe`)
has **untracked June work that is NOT on the Mac**, including:
- `STAGE1_alloy/models/STT_6_core.als`, `STAGE1_alloy/models/STT_6_multisource.als`  ← **`.als` — protected**
- `STAGE1_alloy/a6DiverseModels.java`, `STAGE1_alloy/stage_pipeline.py`, new `.pyc`s
- modified `check_ld_*` / `STATUS.md` / `claudelog.md` / `claudenotes.md` / `docs/`

If the Mac is declared source of truth and force-synced, **this work is destroyed.** So before any
sync or cleanup: diff both trees, surface every file that exists only on cafe2 or differs, and get
Anna's decision per file (bring to Mac / keep only on cafe / dead). Treat the `.als` files with
rule #1. Produce the diff; do not resolve it unilaterally.

## The target layout (where things go)

The `wiki/` scaffold already exists. Consolidate markdown into it (propose, don't auto-move):
- `wiki/state/` — living, overwrite-in-place: `STATUS.md`, `RUNNING.md`, `INFRA.md` (done), `OPEN.md`
- `wiki/design/` — durable semantics: `DESIGN.md`, `AUDIT.md`, `METHODS_*.md`, stage docs
- `wiki/findings/` — per-bug / per-result writeups: the `bug/` tree + `mdsToRead/*`
- `wiki/logs/` — append-only `claudelog.md` + ephemeral `claudenotes.md`
- `wiki/README.md` — the index (exists)
- run writeups (`results.md`, `reconresults.md`, `PAPER_RESULTS.md`, `EXPERIMENTS.md`, …) → decide
  with Anna: `wiki/findings/` vs a `wiki/results/` bucket.

**Migration has a cost:** `claudelog.md` / `claudenotes.md` / `STATUS.md` at the repo root are
referenced by `CLAUDE.md`, the sweep watchers, and `dashboard.py` (`DASHBOARDS` → `CODE_ROOT/
STATUS.md`). If one moves, **every reference must move with it in the same step.** Enumerate the
references before proposing a move. When unsure, leave it at root and link from the wiki instead.

## The walkthrough protocol (how to work with Anna)

1. **Inventory.** Build a table of every non-generated file (skip `testsets/`, `results/`,
   `generated/`, `.git/`, `__pycache__`): path, size, last-modified, tracked/untracked, one-line
   "what is this", and a guess at **status** = `current` / `stale` / `superseded-by-X` /
   `duplicate-of-Y` / `dead` / `unknown`. Cross-check against `claudelog.md` to date things.
2. **Walk it with her, in priority order:** (a) the divergence reconciliation above; (b) scattered
   root `.md`; (c) scattered root `.py` (note: `dashboard*.py`, `jobs_registry.py`,
   `simspect_paths.py`, `sweep_monitor.py` are the current dashboard set, Oct 13 — likely keep;
   `archive/`, `old/` — likely dead, confirm); (d) `STAGE*/`, `runconfigs/`, `bug/`, `docs/`,
   `mdsToRead/`, `paper_figures/`. For each: state your read, propose a destination/action, wait.
3. **Record every decision** in `wiki/logs/claudelog.md` (append-only, dated) and reflect the new
   map in `wiki/README.md` as you go — so the cleanup itself is not lost to session state.
4. **Execute only what Anna approves**, and let *her* run git. After moves, fix all references and
   verify: `make status`, `python3 dashboard.py --selftest`, and a dry pipeline import still work.

## Known context (don't re-derive)
- Infra/sessions: see `wiki/state/INFRA.md`. Rig is live (`make status`). Last real work 2026-06-10
  (`sptDiscrepancy`), open item: 24 untriaged `str` store-addr hits (needs a store-transmitter checker).
- The container has accumulated **zombie processes** (`rg <defunct>`, old `MainThread`) — harmless
  but note them; a container-side cleanup may be worth proposing.
- Dashboard renders markdown natively but has **no `vscode://` open-in-VSCode links** — adding them
  (local files → `vscode://file/<abs>`; cafe2 artifacts → `vscode://vscode-remote/ssh-remote+cafe2/<abs>`;
  `.md` keeps rendering natively) is a tracked work item; scope it with Anna.

## Deliverables
1. The inventory table (write it to `wiki/state/REPO_MAP.md`).
2. The Mac↔cafe2 divergence diff + per-file decisions (logged).
3. The approved, executed consolidation (references fixed, dashboard/selftest green).
4. `wiki/README.md` updated to the final map; dead files quarantined to `old/`/`archive/` (not
   deleted) unless Anna says delete.
