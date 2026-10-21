# COMMANDS — every `make` target (the command reference)

*Living doc. **Keep this in sync whenever a Makefile target or `scripts/sim` command changes** —
see the "Documentation is proactive" directive in the root `CLAUDE.md`.*

Variables (override on the command line): `MODEL` (Alloy stem), `CONFIG` (generation config),
`RUNCONFIG` (gem5 execution config), `FORCE=1` (re-run even if output exists), `PORT`, `W` (tmux
window for `peek`), `CMD` (command string for `launch`). Defaults: `MODEL=STT_6`,
`CONFIG=runconfigs/run_config_STT_6.jsonc`, `RUNCONFIG=$(CONFIG)`.

## Sessions / infra — connect-or-create the rig from anywhere
These wrap `scripts/sim` (config in `scripts/simspect.env`). Full runbook: [`INFRA.md`](INFRA.md).

| command | what it does |
|---|---|
| `make hold` | Ensure the detached Slurm holder job (`hold_simspect`, 32G, 2-day) owns cafe2. Renew when it expires. |
| `make cafe` (= `make sess` / `make session`) | Attach the persistent `work` tmux in container `gem5_dev` (creates job + tmux if missing). `Ctrl-b d` detaches; runs keep going. |
| `make status` | Holder job + `docker ps` + tmux sessions + any live pipeline/gem5/sweep processes. |
| `make launch CMD="…"` | Run `CMD` in a NEW `work` tmux window (survives drops); logs to `run_<win>.log`. |
| `make peek W=<win>` | Print the tail of the `work` session (or window `W`) — watch without attaching. |
| `make windows` | List windows in the `work` session. |
| `make dash` | **Always kills any running dashboard and restarts from current code**, binds the container bridge IP (`172.17.0.2`), forwards `:8765`, opens the browser. (The kill+restart stops a stale old process masking new UI after a pull.) |
| `make sync [M="note"]` | **Sync git everywhere:** commit (if dirty) + push `main` from local, then **fast-forward-only** pull on cafe2 and the mini. Never force/merge — if a side can't fast-forward it says so and you resolve it. `M=` sets the commit message (default: `sync: <host> <time>`). |
| `make mini` | Attach the always-on driver tmux (`simspect`) on the Mac mini (creates if missing). |
| `make mini-clone` | One-time: clone the driver harness onto the mini (`~/simspect`; source-only — heavy dirs are gitignored; `-A` forwards your GitHub key). |
| `make mini-ssh-help` | Print the one `ssh-copy-id` command *you* run to enable key auth to the mini. |
| `make mini-bootstrap` | Copy `~/.ssh/config` + sc key to the mini so IT can reach cafe2. |

## Generation + run — the recommended pipelined flow
| command | what it does |
|---|---|
| `make gen MODEL=<stem> CONFIG=<gen.jsonc>` | Producer: `xml`+`llvm`+`asm` run **concurrently** (all stages stream), resumable, no gem5. Writes `testsets/<MODEL>/`. |
| `make run MODEL=<stem> RUNCONFIG=<build.jsonc>` | Consumer: gem5 sweep; results split **by transmitter kind** into `results/<name>__<ts>/<mode>/<kind>/`. One per build; run several (different `RUNCONFIG`) against one `MODEL` concurrently. |
| `make pipeline MODEL=… CONFIG=… RUNCONFIG=…` | Producer (background) + one consumer (foreground). |

## Low-level engine — single build, sequential (what the watchers use)
| command | what it does |
|---|---|
| `make all MODEL=… CONFIG=… [FORCE=1]` | `pipeline.py all` — phases xml→llvm→asm→gem5 in sequence. |
| `make xml` / `make llvm` / `make asm` / `make gem5` | Run one phase (`pipeline.py <phase>`). Idempotent/resumable; `FORCE=1` to regenerate. |
| `make clean MODEL=… CONFIG=…` | `pipeline.py clean` for that model/config. |

## Dashboard (direct)
| command | what it does |
|---|---|
| `make dashboard [PORT=9000]` | Run `dashboard.py` locally on the box where the data lives (binds loopback). Use `make dash` instead to also handle the cafe2 forward. |

## Help
`make help` — prints the recommended flow. `scripts/sim help` — prints the session-command list.
