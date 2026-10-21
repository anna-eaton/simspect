# INFRA — connect to the rig & run experiments (the session runbook)

*Living doc — keep current. This is the source of truth for how to reach compute and start work.
Everything here is connect-or-create and driven from the Makefile; nothing depends on a live
session you can't recreate.*

## The topology

```
  your laptop ──┐
                ├─ Tailscale ─→  Mac mini (annas-mac-mini)   ← always-on DRIVER (persistent tmux)
  (ephemeral)   │                        │
                │                        └─ ssh ─┐
                └──────── ssh ──────────────────┤
                                                 ▼
                                   sc.stanford.edu  (Slurm login / jump host)
                                                 │  ProxyJump
                                                 ▼
                                   cafe2.stanford.edu  (Slurm COMPUTE node)
                                                 │  docker exec
                                                 ▼
                                   container gem5_dev  (image: recon)
                                                 │  tmux  (survives every disconnect)
                                                 ▼
                              /tests/simspect  ← repo; gem5 + pipeline run here
```

**Code source of truth = local (this Mac).** cafe2 syncs via `git pull`. Do **not** push from the
container. (⚠️ one-time reconciliation pending — see `REPO_CLEANUP_BRIEF.md`: the container has
untracked June work, incl. `.als` files, that is NOT on the Mac. Reconcile before overwriting.)

## Why it used to keep breaking

cafe2 enforces **`pam_slurm_adopt`**: you may only SSH/VSCode into it **while you hold a Slurm
job there**. The old flow used `srun --pty bash`, whose job *is* the terminal — when VSCode's SSH
dropped, that bash got SIGHUP → the job ended → the node was released → every other session was
instantly kicked (`no active jobs on this node`), killing runs. **Fix:** a *detached holder job*
(`sbatch … sleep infinity`) owns the node independent of any connection; all real work runs inside
**tmux inside the container**, so a drop costs nothing — reattach and everything is still running.

## Everything is a `make` target (wraps `scripts/sim`; config in `scripts/simspect.env`)

| command | what it does |
|---|---|
| `make hold`    | Ensure the detached Slurm holder job (`hold_simspect`, 32G, 2-day) owns cafe2. Renew by re-running when it expires. |
| `make cafe`    | Attach the persistent `work` tmux inside `gem5_dev` (creates holder job + tmux if missing). `Ctrl-b d` detaches; runs keep going. Alias: `make sess`. |
| `make status`  | Holder job + `docker ps` + tmux sessions + any live pipeline/gem5/sweep processes. **"Know exactly what we're running."** |
| `make launch CMD="…"` | Run a command in a NEW `work` tmux window (survives drops); logs to `run_<win>.log`. e.g. `make launch CMD="python3 pipeline.py all --model STT_6 --config runconfigs/run_config_STT_6.jsonc"` |
| `make peek W=<win>` | Print the tail of the `work` session (or window `W`) — watch a run without attaching. |
| `make windows` | List windows in the `work` session. |
| `make dash`    | Start the dashboard in the container (if needed) + forward `:8765` + open the browser. |
| `make mini`    | Attach the always-on driver tmux (`simspect`) on the Mac mini (creates it if missing). |

### Reattach after ANY disconnect
```bash
make cafe          # or, raw:  ssh -t cafe2 'docker exec -it gem5_dev tmux new -A -s work'
```
If it says *"no active jobs on this node"* the holder job expired → `make hold` then `make cafe`.

## One-time setup

### 1. cafe2 / sc — already working
`~/.ssh/config` has `sc` (login, key `~/.ssh/sc`) and `cafe2` (`ProxyJump sc`). Nothing to do.

### 2. Mac mini as the always-on driver — needs key auth (currently password-only)
The mini account `annaeaton` exists but only accepts passwords. Enable key auth **(run this
yourself — it needs the mini's password; Claude cannot type it):**
```bash
# if the mini refuses connections at all: System Settings → General → Sharing → Remote Login = ON
ssh-copy-id -i ~/.ssh/id_ed25519.pub annaeaton@annas-mac-mini.taila6e9af.ts.net
make mini            # should now attach the 'simspect' tmux on the mini
```
Then give the mini its own path to cafe2 (so it can be the driver):
```bash
make mini-bootstrap  # copies ~/.ssh/config + sc key to the mini; then on the mini: scripts/sim status
```
**Driver pattern:** on the mini, `make cafe` (or `make launch …`) inside its persistent `simspect`
tmux. The mini stays up, so the SSH→cafe2→tmux chain survives your laptop sleeping; you just
`make mini` to look in. Long sweeps keep running regardless of the laptop.

## Dashboard (what it is)

Stdlib-only web console (`dashboard.py` + `dashboard_data.py` + `dashboard_ui.py`), loopback-only,
reached via the port-forward `make dash` sets up. Panels: Alloy **Generation**, **Fanout**/
concretization, **gem5 campaigns/jobs** (live "what's running"), a **Corpora** browser (per test:
XML / `.ll` / `.s` / `.ann.json`), utilities (annotation & checker viewers, instruction tables,
launch-fanout, exec-graph stub), and **consolidated docs** — it renders any linked **markdown
natively**. `make dash` starts it detached inside the container bound to the **bridge IP**
(`172.17.0.2`, not loopback — so the `ssh -L` forward can reach it), logs to
`/tests/simspect/dashboard.log`, health-checks it, then forwards `:8765` to your laptop. (The
container has no `ss`/`netstat`, so the up-check uses `curl`.) It renders markdown
natively** (`/api/md`). **Gap vs. the goal:** non-markdown files are viewed inline but there are no
`vscode://` "open in VSCode" links yet — adding those (local path → `vscode://file/…`; container
artifacts → `vscode://vscode-remote/ssh-remote+…`) is a tracked work item (see the cleanup brief).

## Container ↔ GitHub auth (deploy key)

The `gem5_dev` container runs as **root** with HOME `/root` (ephemeral — not a mount), while
`/tests` and `/work` are the **persistent** mounts. So GitHub credentials must live on a
persistent mount or they die on container rebuild. Set up 2026-10-20:

- **Repo-scoped deploy key** (ed25519) at `/work/.ssh/simspect_deploy` (+ `.pub`), persistent.
- Repo points at it via `git -C /tests/simspect config core.sshCommand`
  `"ssh -i /work/.ssh/simspect_deploy -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"`
  (lives in `.git/config` on the persistent `/tests` mount).
- Public key is registered on GitHub → repo `anna-eaton/simspect` → Settings → **Deploy keys**
  (write access). Blast radius = this repo only.
- **If the repo is ever re-cloned fresh in the container**, re-run the `core.sshCommand` config
  (the key on `/work` survives; only `.git/config` is lost on re-clone).
- Test read-only: `git -C /tests/simspect ls-remote origin`.

Sync model: the container can now `git fetch`/`push` directly. (Fallback that needs no container
creds: `git bundle` in/out through the Mac, which has its own GitHub auth.)
