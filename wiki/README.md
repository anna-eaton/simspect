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
| **Design / semantics** | [`design/`](design/) | `DESIGN.md`, `AUDIT.md`, `METHODS_{CONCRETIZATION,INSTRUMENTATION,LEAKAGE_KNOBS}.md`, `branch_enumeration_notes.md`, `sweep_design_notes.md`, `SPEC_PRIMITIVE_INSTANCES.md` (every speculation-primitive instance, for the paper table), `STL_SPECULATION.md` (store-to-load speculation: `STT_6_stl.als`, the `stl_bypass` concretization mode, the SimSpect-STL gem5 hooks, the proposed window check), `SIMSPECT_HOOKS.md` (the `O3PipeView:simspect:` cache/defense event trace built into the amulet InvisiSpec/CleanupSpec/SpecLFB gem5 builds), `docs/` (scope/criterion). The stable reference. |
| **Models & builds** | [`design/MODELS_AND_BUILDS.md`](design/MODELS_AND_BUILDS.md) | What every Alloy model encodes (defense + leakage + driver, latest models first) and every gem5 build + its intention. |
| **Pending `.als` edits** | [`state/ALLOY_MODEL_CHANGES.md`](state/ALLOY_MODEL_CHANGES.md) | Owner-gated Alloy changes to **block out** known false-positive shapes (const-addr / no_hold / rf-clobber) + coverage edits, each grounded in a findings doc, with the STT/SPT rerun cost. |
| **Run results** | [`results/`](results/) | Campaign/paper writeups: `results.md`, `reconresults.md`, `PAPER_RESULTS.md`, `PAPER_EXPERIMENTS.md`, `EXPERIMENTS.md`. |
| **To write up (paper)** | [`results/TO_WRITEUP_PAPER.md`](results/TO_WRITEUP_PAPER.md) | Running list of findings/arguments to lift into the S&P 2027 paper. First item: MCM litmus count vs. SimSpect count (cycle- vs path-based minimality). |
| **Findings / bugs** | [`findings/`](findings/) | `bug/` (per-bug writeups + PoC demos) and `mdsToRead/` (analysis docs). |
| **Footprint-defense scope** | [`findings/mdsToRead/PROTECTION_SCOPE_TABLE.md`](findings/mdsToRead/PROTECTION_SCOPE_TABLE.md) | Per-structure table for InvisiSpec / SpecLFB / CleanupSpec: what each paper promises, what the build implements (file:line + flag), what AMuLeT checks, what our runs enable; plus the four `results/STT_6_*_full*` run configs (not launched). Background: `FOOTPRINT_DEFENSES_PAPER_AUDIT.md`. |
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
