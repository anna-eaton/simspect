# RUNNING — what is live right now

*Living doc, overwrite-in-place. Refreshed by `/session-log`. Always re-verify with `make status`
before trusting — this is a snapshot, not a daemon.*

*Snapshot: 2026-10-20 19:45 — session `system setup`.*

## Slurm allocation (the holder job)
- **Job `17995019`** — `hold_simspect`, partition `cafe-interactive`, node **cafe2**, 32G,
  2-day limit, started ~2026-10-20 15:51 (running ~3h54m at snapshot). Owns the node so SSH/docker
  survive disconnects.
- **Renew when it expires:** `make hold`.  **Check:** `make status` (or `ssh sc squeue --me`).

## Experiments
- **None running.** `make status` → "(none running)". Clean slate for the next sweep.

## Dashboard
- **Live** in container `gem5_dev` on cafe2, bound to the bridge IP **172.17.0.2:8765**
  (the Oct-13+ 3-tab build with VSCode deep links — NOT the old June one).
- **Reach it:** `make dash` (kills any running instance, restarts from current code, forwards
  `:8765` to your laptop, opens the browser). **Log:** `/tests/simspect/dashboard.log` in the container.

## Persistent sessions (tmux)
- Container `gem5_dev`: tmux **`work`** (where experiments run). Attach: `make cafe`.
- Mac mini: tmux **`simspect`** (always-on driver). Attach: `make mini`.

## Notes
- The container has accumulated `<defunct>` zombie processes (no init/reaper in the image) from
  repeated dashboard restarts + ssh execs — **harmless**, but see `OPEN.md` for the optional cleanup.
