# SimSpect Wiki — start here

The organized, durable **source of truth** for project state. Governing principle (see root
`CLAUDE.md` → *Write everything down*): if it matters, it lives in a file here — not in a chat,
a terminal, or a tmux pane that can die. A new session reconstructs reality from this wiki + the
append-only logs, never from "what the last session remembered."

## Map

| area | where | what |
|---|---|---|
| **Connect / run** | [`state/INFRA.md`](state/INFRA.md) | How to reach compute & run experiments. `make hold / cafe / status / dash / mini`. Read this to start working. Includes container↔GitHub deploy-key auth. |
| **Repo map** | [`state/REPO_MAP.md`](state/REPO_MAP.md) | Inventory of every non-generated file + status. |
| **Sync state** | [`state/SYNC_DIVERGENCE.md`](state/SYNC_DIVERGENCE.md) | Mac↔cafe2 reconciliation (resolved) + gem5-hook durability (open). |
| **What's live now** | `state/RUNNING.md` *(to create)* | Current allocations, campaigns, sweeps. Verify with `make status`. |
| **Human rollup** | [`../STATUS.md`](../STATUS.md) | The one-page "where everything stands" for Anna. **Stays at repo root** (dashboard reads `CODE_ROOT/STATUS.md`). |
| **Open questions** | `state/OPEN.md` *(to create)* | Decisions awaiting Anna. |
| **Design / semantics** | [`design/`](design/) | `DESIGN.md`, `AUDIT.md`, `METHODS_{CONCRETIZATION,INSTRUMENTATION,LEAKAGE_KNOBS}.md`, `branch_enumeration_notes.md`, `sweep_design_notes.md`, `docs/` (scope/criterion). The stable reference. |
| **Run results** | [`results/`](results/) | Campaign/paper writeups: `results.md`, `reconresults.md`, `PAPER_RESULTS.md`, `PAPER_EXPERIMENTS.md`, `EXPERIMENTS.md`. |
| **Findings / bugs** | [`findings/`](findings/) | `bug/` (per-bug writeups + PoC demos) and `mdsToRead/` (analysis docs). |
| **Logs** | `logs/` *(claudelog/claudenotes stay at root — code refs; link here)* | `../claudelog.md` (durable, append-only) + `../claudenotes.md` (right-now). |
| **Repo cleanup** | [`REPO_CLEANUP_BRIEF.md`](REPO_CLEANUP_BRIEF.md) | Brief for the agent auditing/consolidating the repo. |

**Stays at repo root (do not move — code/CLAUDE.md reference them):** `CLAUDE.md`, `STATUS.md`,
`claudelog.md`, `claudenotes.md`. Everything else that was loose at the root has been migrated into
`design/`, `results/`, and `findings/` above — including the former root dirs `bug/` + `mdsToRead/`
(→ `findings/`) and `docs/` (→ `design/docs/`).

## The three durability mechanisms
1. **Append-only logs** (`logs/claudelog.md`) — the dated narrative of what happened/changed/was decided.
2. **Living state docs** (`state/*`) — current truth, overwritten in place.
3. **Build/result provenance** — every campaign keeps its `run_config.jsonc` + an md note of what
   build it is and why, so results reproduce from disk (see `CLAUDE.md` → "reproduce EXACTLY as the
   config did").
