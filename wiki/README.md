# SimSpect Wiki — start here

The organized, durable **source of truth** for project state. Governing principle (see root
`CLAUDE.md` → *Write everything down*): if it matters, it lives in a file here — not in a chat,
a terminal, or a tmux pane that can die. A new session reconstructs reality from this wiki + the
append-only logs, never from "what the last session remembered."

## Map

| area | where | what |
|---|---|---|
| **Connect / run** | [`state/INFRA.md`](state/INFRA.md) | How to reach compute & run experiments. `make hold / cafe / status / dash / mini`. Read this to start working. |
| **What's live now** | `state/RUNNING.md` *(to create)* | Current allocations, campaigns, sweeps. Verify with `make status`. |
| **Human rollup** | `../STATUS.md` *(migrating → `state/STATUS.md`)* | The one-page "where everything stands" for Anna. |
| **Open questions** | `state/OPEN.md` *(to create)* | Decisions awaiting Anna. |
| **Design / semantics** | `design/` *(migrating)* | `DESIGN.md`, `AUDIT.md`, `METHODS_*`. The stable reference. |
| **Findings / bugs** | `findings/` *(migrating)* | Per-bug & per-result writeups (`bug/`, `mdsToRead/`). |
| **Logs** | `logs/` *(migrating)* | `claudelog.md` (durable, append-only) + `claudenotes.md` (right-now). |
| **Repo cleanup** | [`REPO_CLEANUP_BRIEF.md`](REPO_CLEANUP_BRIEF.md) | Brief for the agent auditing/consolidating the repo. |

*Much legacy markdown still lives at the repo root and is being consolidated here per the cleanup
brief — until each file is migrated (with its references fixed), the root copy stays canonical.*

## The three durability mechanisms
1. **Append-only logs** (`logs/claudelog.md`) — the dated narrative of what happened/changed/was decided.
2. **Living state docs** (`state/*`) — current truth, overwritten in place.
3. **Build/result provenance** — every campaign keeps its `run_config.jsonc` + an md note of what
   build it is and why, so results reproduce from disk (see `CLAUDE.md` → "reproduce EXACTLY as the
   config did").
