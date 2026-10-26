# OPEN — pickup list (TODOs + questions for Anna)

*Living doc, overwrite-in-place. The place leftover work lands so it survives a killed session.
Dated, grouped. Refreshed by `/session-log`. Newest context at top of each group.*

## 🔴 Critical — owner: Anna (git write lock in force; Claude is read-only on git)
- **Recover git after the disk-full corruption (2026-10-20).** A 98%-full-disk event corrupted git
  objects and an **empty-tree commit was pushed to all remotes**. Symptoms: locally `git ls-files`
  = 0, `HEAD` tree empty, yet "up to date with origin/main". **All working-tree files are intact on
  disk** (just untracked) — nothing is lost locally. Needs a careful restore of a good tree + push,
  by Anna. Until then the repo is untracked; `/session-log` writes are plain files on disk (safe).
  ⚠️ During recovery, make sure the container's untracked June work is preserved — esp. the `.als`
  models `STAGE1_alloy/models/STT_6_core.als`, `STT_6_multisource.als` (approval-only; see
  `wiki/state/SYNC_DIVERGENCE.md`).
- **The `GIT WRITE LOCK`** is now in `CLAUDE.md` (top), `~/Documents/CLAUDE.md`, and memory
  (`git-write-lock`). Claude hands git-write commands to Anna; never runs them.

## Infra follow-ups
- **`make mini-clone`** (after `make mini-bootstrap`) — give the Mac mini the driver-harness clone
  so `make sync` reaches it and the mini can drive cafe2. (Deferred — blocked until git is recovered,
  since cloning from a corrupted remote would pull the bad tree.)
- **Persistent Claude on the mini** — the always-on driver: a long-lived Claude in the mini's
  `simspect` tmux so work continues with the laptop closed. Set up after the clone exists.
- **Verify the dashboard VSCode links end-to-end** from the laptop (Remote-SSH URIs
  `vscode://vscode-remote/ssh-remote+cafe2/…` for container files; `vscode://file/…` for local).
  The 3-tab redesign + links are deployed and serving; confirm clicking actually opens VSCode.
- **Container zombie cleanup** (optional): `gem5_dev` accumulates `<defunct>` procs (no reaper).
  Harmless; a `docker restart gem5_dev` (when nothing's running) or adding `tini` would clear it.

## Pending Alloy model edits (owner-gated — Anna's sign-off per change)
- **Full list → [`ALLOY_MODEL_CHANGES.md`](ALLOY_MODEL_CHANGES.md)** (created 2026-10-26). The `.als`
  changes to **block out** the known false-positive shapes we triaged on STT/SPT, so re-enumeration
  stops regenerating artifacts we then re-triage. Highest priority:
  - **A1 — source-derived taint closure** (fixes const-addr FPs ~99.9% of SPT `ld` + SPT-Fence
    `no_hold`): seed protset from `Loads.outreg`+memory only, forward closure, union semantics.
  - **A2 — `rf` most-recent-writer fact** (fixes clobber, ~58.6% of `SPT_6_oneLP`): forbid an
    intervening same-state writer; Option A validated on a copy (still SAT).
  - Plus coverage edits (B1–B5: diversity driver, joint minimality, instruction-minimality, var
    length, extended vocabulary) and the rerun matrix.
  - **Rerun cost:** each is a Stage-1 change → full STT + SPT regen (`xml --force`) + re-sweep. Batch
    the edits so we pay the regen once. Nothing applied yet — show Anna the diff and wait.

## Research (carried forward — pre-dates this session)
- **24 `str` (store-addr) hits untriaged** (from 2026-06-10 `sptDiscrepancy`): they fall through to
  `check_ld` (wrong criterion) and `bucket_hits.py` is ld-only. Needs a **store-transmitter
  checker/diag**. See `claudelog.md` (06-10 entries) + `wiki/state/SYNC_DIVERGENCE.md`.
- **Next experiments** (none launched this session — "decide after seeing state"): branch-hit
  sweeps / resolved-br windows, and the natural + short-timing sweeps, per Anna's TODO in `STATUS.md`.

## Dashboard / views follow-ups
- **Consolidate enumeration so we don't enumerate a model "by bound."** Right now a model is
  enumerated at a fixed instruction scope (`exactly 6 Instruction`), and the dashboard model views
  treat each bound as its own corpus. Eventually we want to **enumerate all bounds together** —
  one logical testset per model spanning its scopes — and the dashboard view should present the
  model as a single consolidated entity (aggregate counts across bounds), not a separate row/corpus
  per bound. (Raised 2026-10-21 while building the Utilities Alloy-models/gem5-builds/hooks tables.)

## Questions for Anna
- After git recovery: is cafe2's container the authority for the untracked June `.als`/`stage_pipeline.py`
  work, or the laptop? (Determines sync direction once git is healthy.)
- Do you want persistent-Claude-on-mini wired now, or only after git + mini-clone are settled?
