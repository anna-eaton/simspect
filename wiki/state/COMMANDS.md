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
| `make gen MODEL=STT_6_stl CONFIG=runconfigs/run_config_STT_6_stl.jsonc` | Store-to-load speculation testset (branch mode `stl_bypass`, output `testsets/STT_6_stl/stl_bypass/`). gem5 build `/work/gem5-recon-stl`. Alloy can't run on cafe2 (no `a6CountModels.class`): run `xml` on the Mac and copy the XML over. The window checker isn't written, so use `stl_hooktest.py` for verdicts. [`design/STL_SPECULATION.md`](../design/STL_SPECULATION.md) |
| run-config keys `fpr` / `reg_naming` (→ `batch_generate.py --fpr-config '<json>'` / `--reg-naming-config '<json>'`) | Opt-in Stage-2 options (2026-11-08). `fpr`: route consumed loads' values through xmm registers (`forms` route/direct/route_alu/direct_alu, `xmm_regs`), recorded in `.ann.json` `fpr`; templates `specs/fanout/fpr.json`, `specs/fanout/fp.json`. `reg_naming: {"mode": "random", "seed": S}`: per-test random x86 names for the locked Alloy registers (`{"mode": "sorted"}` = legacy map + record). Absent = byte-identical legacy output. [`design/VOCAB_TABLES.md`](../design/VOCAB_TABLES.md) "FPR (xmm) routing" |
| FP-mode corpus `MODEL=STT_6_fp` with `runconfigs/fixed_20261030/STT_6_fp_stt_latest.jsonc` | Separate FP corpus (never mixed into STT_6): `testsets_latest/STT_6_fp` with `xml -> ../STT_6/xml`, then `pipeline.py llvm` / `asm` / `make run`. The recipe is in the config header. Built 2026-11-08 for the 0.02-sample stems only. |
| `python3 STAGE2_compilation/proposed/measure_xmit_path_alu.py <xml_dir> [--n 300] [--variants 4] [--interleave-config <cfg>]` | Read-only fanout-v2 measurement: how often each interleave approach (none / current / random-anywhere / read-only fillers / edge splice) puts an ALU op on the transmitter's address path and keeps every Alloy edge. [`design/VOCAB_TABLES.md`](../design/VOCAB_TABLES.md) "Fanout v2 proposal" |
| `python3 STAGE2_compilation/audit_commit_boundary.py testsets/<model> [...]` | Check that every test's lc/fnc is an Alloy instruction, not an interleave chain step or synthetic NOP; exit 1 and list offenders if not. Testsets interleaved before 2026-10-29 fail and need regenerating from `llvm`. [`design/COMMIT_BOUNDARY.md`](../design/COMMIT_BOUNDARY.md) |
| `python3 STAGE3_gem5/hook_audit.py --build <name\|a,b\|all> --testset testsets/<model> [--n 6] [--S 200] [--F 150] [--jobs N] [--keep] --out audit.json` | (in the container) Run each test with one hook at a time (none / raw annotation / aliased / resolve stall / resolved stall / fnc stall / production force plan) and check every hook changes the pipeline as claimed; per-variant trace fingerprints prove a rebuild is print-only by diffing two audit JSONs. Builds listed in its `BUILDS`. [`design/RESOLUTION_HOOKS.md`](../design/RESOLUTION_HOOKS.md) §4 |
| `gem5-hooks/resolve/rebuild_resolve_hooks.sh <build>` | (in the container) Back up the binary (`gem5.opt.pre-resolve-hooks-20261030`) and the 3 source files (`/work/simspect_backups/resolve-hooks-20261030/`), apply `gem5-hooks/resolve/apply_resolve_hooks.py` (BR resolve lines + forced-not-taken), rebuild with scons. Log in the backup dir. Rollback steps in RESOLUTION_HOOKS.md §5. |
| `STAGE3_gem5/triage/run_spt_brx_triage.sh <campaign> <config> <testset_root> <outdir> [jobs]` (+ `hit_facts.py`, `spt_cond_slice.py`, `spt_taint_probe.py --stems inst-N:grid`, `fnc_commit_check.py`, `testset_provenance.py`) | (in the container, fixed repo copy) Hit triage for fixed-harness campaigns. Per-hit facts, an x86 slice with gem5-spt's taint rules, faithful re-runs at the hit's grid point that read gem5's own "made pending" lines and SPT stats, fnc commit ticks, and testset provenance hashes. [`findings/bug/BRANCH_ANNOTATION_AND_FORCE.md`](../findings/bug/BRANCH_ANNOTATION_AND_FORCE.md) §7 |
| `STAGE3_gem5/triage/diag/` → `results/<campaign>/diagnostics/` then `python3 bucket_hits.py --xml-dir <testset>/xml` | Per-results classifying scripts for the fixed harness. `bucket_hits.py` buckets every transmitter kind (diagnostics declare `KINDS`, `MODE`). New: `diag_brx_const_condition`, `diag_brx_declassified_condition` (SPT, evidence `spt_brx_evidence.json`), `diag_recon_stlf_bypass` (recon-modded real bug A2, evidence `recon_stlf_evidence.json`). [`STAGE3_gem5/triage/diag/README.md`](../../STAGE3_gem5/triage/diag/README.md) |
| `runconfigs/fixed_20261030/*.jsonc` | Fixed-harness campaign configs (fnc stall 0, derived force, validity gate, 2% sample): `STT_6_stt_fixed`, `STT_6_reconmodded_fixed`, `SPT_6_oneLP_fence_fixed`, `STT_6_interleave_reconmodded_fixed`, `STT_6_commitsplit_stt_fixed`. The `*_fixed_latest` variants run on `testsets_latest/` (current models); the plain ones use the pre-06-03 `testsets/`. Run with `make run MODEL=… RUNCONFIG=…` once synced. |
| `scripts/archive_results_pre_resolve_hooks.sh [--delete]` | (in the container) Zip every pre-2026-10-30 `results/` campaign to `archive/results_pre_resolve_hooks_20261030.zip` and verify it. `--delete` (Anna only) then removes the bulky outputs, keeping each run's configs, mds and `diagnostics/`. Log next to the zip. |
| `python3 gem5-hooks/stl/apply_stl_hooks.py <gem5_root> [--dry-run]` | Insert the SimSpect-STL gem5 hooks (store address-generation hold + memory-dependence prediction override; flags `--stl-ann-file`, `--stl-store-stall-cycles`, `--stl-alias-pred`) into a gem5 tree, then rebuild. Idempotent; originals saved as `*.pre-stl`. Build with `/usr/bin/scons build/X86/gem5.opt -j 48` (the `/usr/local/bin/scons` 2.5.1 fails on Python 3.8). |
| `LC_ALL=C.UTF-8 SIMSPECT_GEM5_BIN=… SIMSPECT_SE_CONFIG=… SIMSPECT_STL_ANN_ENABLE=1 SIMSPECT_STL_ALIAS_PRED=no_alias SIMSPECT_STL_STORE_STALL_CYCLES=5000 python3 gem5-hooks/stl/stl_hooktest.py <testdir> <scheme> <out.json>` | Run an `stl_bypass` testset dir (`asm/` + `ann/`) on a SimSpect-STL build and report hold/bypass/squash validity and whether each load transmitter really sent to memory inside the hold. Without `LC_ALL=C.UTF-8`, recon's `se.py` (non-ASCII line 128) crashes gem5's Python. |
| `python3 STAGE1_alloy/model_source_matrix.py <model.als>... [--only br_only,str_only,...] [--limit N] [--keep DIR] [--jobs 6] [--timeout 1800]` | For each model and each speculation-source kind (branch / store / store with or without a true alias, `rf`-based or, with `str_alias_atom`, by shared `Mem_s` atom / load / ALU / branch + store), ask Alloy for instances of `gen_useful_litmus` restricted to that kind and print SAT / UNSAT / TIMEOUT (unknown). Models are never modified (temp copies). `--keep` saves the witnesses, which `batch_generate.py` can concretize. Run on the Mac. Also: `gem5.config_script: /work/stt/configs/example/se_futuristic.py` runs `/work/stt` under STT-Futuristic. [`design/STT_VS_RECON_STT.md`](../design/STT_VS_RECON_STT.md) |
| `python3 STAGE1_alloy/models/proposed/derive_stl.py <main>.als <out>.als [--alias atom\|rf]` | Derive the STL (store-to-load speculation) draft of a main Alloy model: exactly the edits that made `STT_6_stl` from `STT_6` (STL source block, all branches resolved, alias fact, contract and branch-keyed protset line switched to stores). Refuses if an anchor doesn't match once. `--alias rf` on `STT_6.als` reproduces `STT_6_stl.als`. Output goes in `proposed/` until Anna approves. Split core of the result: `proposed_twophase/derive_core.py <stl>.als <out> --minimality ri`; Stage-1 run: `proposed_twophase/run_stage1.py` (logs `~/Library/Logs/simspect/twophase_<name>.log`). Manifest: `STAGE1_alloy/models/MANIFEST.md`. |

## Low-level engine — single build, sequential (what the watchers use)
| command | what it does |
|---|---|
| `make all MODEL=… CONFIG=… [FORCE=1]` | `pipeline.py all` — phases xml→llvm→asm→gem5 in sequence. |
| `make xml` / `make llvm` / `make asm` / `make gem5` | Run one phase (`pipeline.py <phase>`). Idempotent/resumable; `FORCE=1` to regenerate. |
| `make clean MODEL=… CONFIG=…` | `pipeline.py clean` for that model/config. |

## Footprint checker (InvisiSpec / SpecLFB / CleanupSpec) — `check_footprint.py` + a criterion JSON
The footprint defenses are checked by ONE generic checker, `STAGE3_gem5/check_footprint.py`, which reads only the O3PipeView trace (normal records + the SimSpect hook lines, `wiki/design/SIMSPECT_HOOKS.md`) and a criterion `specs/leakage/{invisispec,speclfb,cleanupspec}.json` (schema and predicates: `wiki/design/TRANSMISSION_CRITERIA_FORMAT.md` "Criterion JSONs + checker"). It needs a hooked build (`amulet-*` after 2026-10-28); on a trace with no simspect lines it returns `status=warn`, `issued_in_window=null`.

| command / key | what it does |
|---|---|
| run_config `gem5.checker: "check_footprint.py"` + `gem5.criterion: "specs/leakage/<defense>.json"` | `pipeline.py gem5` (and `make run`/`testrun.py`, which call it) sends **every** test to that checker instead of the per-kind table (`_checker_for`); `criterion` becomes env `SIMSPECT_CRITERION`. Absent → unchanged kind-table behavior. |
| run_config `gem5.criterion_actor: "spec" \| "futuristic"` | Optional override of the actor mode (env `SIMSPECT_CRITERION_ACTOR`); default = the criterion's `actors.select_by_scheme` on the last `--scheme=<Name>` in `extra_args` (InvisiSpec: `FuturisticSafeInvisibleSpec` → `futuristic`). |
| `python3 STAGE3_gem5/check_footprint.py <dir> --criterion specs/leakage/<d>.json [--jobs N] [--scheme N] [--out r.json] [--actor M]` | Same CLI shape as `check_ld.py`; builds + runs gem5 via `gem5_common` (mirror the campaign's env as usual). Records carry `issued_in_window` (= `leak`), `terms_fired`, `offending` (struct, line, event ids), and for CleanupSpec `per_line` counts, `skip_drop`, `net_state`, `inconsistent`. |
| `python3 STAGE3_gem5/check_footprint.py --trace pipeview.txt --meta meta.json --criterion <json> [--out r.json]` | Offline: evaluate an existing trace, no gem5 (meta = `lc_pc`, `fnc_pc`, `unresolved`, `ticks_per_cycle`, `cmd`). |
| `python3 STAGE3_gem5/tests/test_check_footprint.py` | Unit tests (synthetic traces) + regression on real hooked traces in `STAGE3_gem5/tests/fixtures/` (UV1 leak, UV6 leak, uv5clean no-leak, uv4split leak, InvisiSpec Futuristic). |

## Dashboard (direct)
| command | what it does |
|---|---|
| `make dashboard [PORT=9000]` | Run `dashboard.py` locally on the box where the data lives (binds loopback). Use `make dash` instead to also handle the cafe2 forward. |
| **Eval manifest** tab (`/api/eval_manifest`, `?part=runs` = live runs only) | The official experiment list and its statuses: eval rows E1..E14 sorted by row (gem5 build/flags, model family, run config, status, blocker; click a row id for the unit inspector), live runs from `specs/eval_runs.json` (each run's status JSON, e.g. `launch_stage1.py`'s `stage1_status.json`: host load with a red CONTENTION badge, STALE if no update for 5 min while partitions run, per-family progress, collapsible per-partition table; polled every 60 s), the AMuLeT-parity T rows, the pending C rows, and the rendered `wiki/state/EVAL_MANIFEST.md`. A status file that only exists in the cafe2 container shows "status not available on this host" elsewhere. |

## Help
`make help` — prints the recommended flow. `scripts/sim help` — prints the session-command list.
