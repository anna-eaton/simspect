# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session notes (inter-session comms)

Multiple Claude sessions may run concurrently. Two files coordinate them — **read both first**:

`claudenotes.md` (repo root) — *ephemeral* low-bandwidth scratchpad for "what I'm doing right now":
- **Read it first** to figure out whether something is already being worked on, what
  files/testsets/runs are mid-modification, or why state looks off.
- **Write a one-line status** of what you're doing *right now* (newest at top,
  `YYYY-MM-DD HH:MM — <session-label> — <what>`), and update/clear it when you finish or move on.

`claudelog.md` (repo root) — *durable, append-only* findings log. This is the priority record.
- **Whenever you figure out something big-picture, write it here**: bugs found (and the
  eventual real-gem5-bug-vs-pipeline-artifact verdict), changes that affect other sessions or
  future runs, structural/methodology fixes, and **any reason a sweep had to be restarted**
  (which models/stages are contaminated, whether `--force` is needed).
- **Every entry is dated** (`## YYYY-MM-DD HH:MM — <session-label> — <title>`), newest at top,
  self-contained, and points to the file/log/line that proves it. Append — don't delete history.
- See the header of `claudelog.md` itself for the full what-belongs / what-doesn't rules.
- Don't duplicate things already in `DESIGN.md` / `AUDIT.md` / `results.md`; cross-reference instead.

## What this is

SimSpect generates **litmus tests for speculative-execution security defenses** and checks whether each test actually leaks on a real (gem5) microarchitecture. The flow is a 4-stage pipeline driven by one orchestrator (`pipeline.py`) and one JSONC config per run:

```
STAGE1_alloy   Alloy model (.als) ──java──▶ inst-*.xml   (one XML per candidate leak instance)
STAGE2_compilation  XML ──parsexml.py──▶ inst-*.ll ──llc/clang──▶ inst-*.s + inst-*.ann.json
STAGE3_gem5    .s + .ann.json ──gem5 O3PipeView──▶ window-results.json  (leak / no-leak per test)
```

The Alloy model is a *symbolic taint/speculation model*: it enumerates instruction sequences where a transmitter operand is provably in the speculative protection set. gem5 is the *ground truth*: it runs each generated program and the per-type checkers decide whether the transmitter actually issued inside the speculative window. **Discrepancies between the two are the research signal** (ONLY when the gem5 lets through a test that the model says is disallowed bc its conservative).

## what I'll use claude to do

Run sweeps (though mostly would like this in scripts) 
inspect hits (cases where gem5 lets a supposed violation occur) to see whether it is an issue with my model's expressivity, a concretization bug, a gem5 instrumentation bug (the hooks we have to insert) or a REAL BUG on the gem5. that is the goal to find, so DO NOT mess wtih the gem5 on any front other than the hooks
DO NOT mess with the alloy models lightly, it is very important to run all edits to them by me
DO NOT go tuning the pipeline to hit or avoid certain bug cases, the point is to be general and comprehensive, only tuning to fix wrong things
I want all pipeline phases to stream so we can start running things immediately
Prioritize writing the most important findings — bugs, changes, big-picture fixes, reasons a
sweep had to restart — to `claudelog.md` (see "Session notes" above for the discipline).

## Commands

Everything goes through `pipeline.py <phase> --model <stem> --config <cfg>` (Makefile wraps it):

```bash
python3 pipeline.py all  --model STT_6 --config run_config_STT_6.jsonc   # phases xml→llvm→asm→gem5
python3 pipeline.py xml  --model STT_6 --config run_config_STT_6.jsonc   # Alloy enumeration only
python3 pipeline.py llvm --model STT_6 --config run_config_STT_6.jsonc   # parsexml: XML → .ll + bare ann
python3 pipeline.py asm  --model STT_6 --config run_config_STT_6.jsonc   # .ll → .s + resolved ann
python3 pipeline.py gem5 --model STT_6 --config run_config_STT_6.jsonc   # gem5 window check
make all MODEL=STT_6 CONFIG=run_config_STT_6.jsonc [FORCE=1]              # equivalent
```

- **Phases are idempotent / resumable**: a phase skips if its output dir is already populated. To *regenerate* (e.g. after editing `parsexml.py` or a `.als` model) you must **delete the stale stage output first, or pass `--force`** — otherwise old artifacts are silently kept. `--force` on `xml` re-runs Alloy; on a later phase it only re-does that phase.
- **`--model` is the `.als` stem** in `STAGE1_alloy/models/` *and* the testset dir name. `paths.results_name` in the config is the (possibly different) results dir name, so one testset can feed several result dirs.
- **Run a single checker directly** (full per-record diagnostics, not just the summarized `window-results.json`):
  ```bash
  python3 STAGE3_gem5/check_ld.py <dir-with-.s-and-.ann.json> --jobs 16 --scheme 2 --out full.json
  ```
  The checker builds each binary, runs gem5, and emits `issued_in_window` plus timing fields. gem5 binary/scheme/flags come from env vars (see below) — set them to match the config you're emulating.

## Pipelined run: producer / consumer (preferred — every stage streams)

`pipeline.py all` runs the four phases as a strictly sequential for-loop — it blocks
inside the XML phase (Alloy's `subprocess.run`) until all instances exist before llvm
even starts, so you can't watch llvm/asm progress until xml is 100% done. Two thin
orchestrators on top of the same engine fix this and decouple generation from execution:

- **`testsetgen.py`** (producer) — runs `xml` in a background thread while `llvm`+`asm`
  drain each instance as it lands, so all three stages progress at once. Imports
  `pipeline.py`'s phase functions unchanged. No gem5, no build target. Resumable
  (llvm/asm skip done stems; xml alone can't resume — Alloy restarts from 0).
  `--follow` mode attaches to XML another process is still enumerating (skip xml, stream
  llvm/asm until killed) — used to start stage 2 while a legacy `pipeline.py all` finishes xml.
- **`testrun.py`** (consumer) — a standalone duplicate of `results/_sweep_watcher.py`
  that (a) partitions results **by transmitter kind** into
  `results/<name>__<ts>/<mode>/<kind>/window-results.json` (kind ∈ `ld`/`br_x`/`other_x`)
  so you inspect ld vs br_x hits without joining back to the annotations, and (b)
  timestamps each campaign with a stable `results/<name>__latest` symlink + a manifest
  recording the build/scheme. Run one per build; launch several against one `--model` to
  compare defenses concurrently. It's a *copy* (not an edit) of `_sweep_watcher.py` so
  in-flight watcher runs are never disturbed.

```bash
make gen   MODEL=SPT_6_oneLP CONFIG=run_config_SPT_6_oneLP.jsonc            # produce testset
make run   MODEL=SPT_6_oneLP RUNCONFIG=results/SPT_6_oneLP_fence/run_config.jsonc   # one build
make pipeline MODEL=... CONFIG=... RUNCONFIG=...                            # producer(bg)+consumer
```

`pipeline.py` stays the reused engine; the legacy single-build `all` and the original
`_sweep_watcher.py` are untouched (older campaigns still use them). Ad-hoc launch scripts
were moved to `archive/`.

## Architecture notes that span files


**Config → env-var bridge.** `pipeline.py:_build_gem5_env` translates `run_config.jsonc` `gem5.*` keys into `SIMSPECT_*` env vars that `STAGE3_gem5/gem5_common.py` reads (`SIMSPECT_GEM5_BIN`, `SIMSPECT_SE_CONFIG`, `SIMSPECT_GEM5_CPU`, `SIMSPECT_GEM5_EXTRA` (0x1f-joined `extra_args`), `SIMSPECT_FNC_COMMIT_STALL_CYCLES`, `SIMSPECT_BRANCH_ANN_ENABLE`). When invoking a checker by hand, replicate these. `--scheme=N` is always appended, but a trailing `--scheme=<Name>` in `extra_args` overrides it (last-wins in optparse).

> **Reproducing a hit/bug by hand: run it EXACTLY as the config did.** A hit only
> means something under the same microarchitectural conditions that produced it.
> Before re-running a single test, mirror the campaign's `run_config.jsonc`: the
> right `gem5.binary`/`scheme`/`extra_args` *and* the full hook state —
> **branch forces** (`branch_ann_enable`/`--branch-ann-file` BTB override, on
> `-modded`/SPT builds) and **the proper stalls** (`fnc_commit_stall_cycles`,
> `sweep.unresolved_stall_cycles`, branch-resolve-stall). Drop any of these and
> the speculative window/branch resolution shifts and the test no longer
> reproduces (or false-reproduces) — you'll mis-attribute the result. Easiest:
> reuse the campaign's `run_config.jsonc` (and `--scheme`) verbatim rather than
> hand-assembling flags.

**Multiple gem5 builds, one harness.** The same testset is run against different defense implementations by swapping `gem5.binary`/`config_script`:
- `/work/gem5-recon`, `/work/gem5-recon-modded` (X86, `X86O3CPU`) — STT/Recon. `--scheme` 0=Unsafe 1=Delay 2=STT 3=DoM. `-modded` adds `--branch-ann-file` BTB override (set `branch_ann_enable: true` *only* for that build — vanilla rejects the flag).
- `/work/stt/build/X86/gem5.opt` — STT build.
- `/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt` (`DerivO3CPU`) — SPT. `se.py` maps `--scheme=2`→`SpectreSafeFence`; `extra_args` selects the variant (`--scheme=SpectreSafeInvisibleSpec`, `--configImpFlow=Lazy`, `--fwdUntaint`/`--bwdUntaint`, etc.).

**Per-mode layout.** Whenever a config sets `speculation.branch_modes`, output is split per mode:
```
testsets/<model>/xml/                      # shared across modes
testsets/<model>/<mode>/{llvm,asm,ann}/    # <mode> = mispredict_not_taken | mispredict_taken
results/<results_name>/<mode>/{window-results.json, window-hits.txt, hits/, sweep/}   # _sweep_watcher.py
results/<results_name>__<ts>/<mode>/<kind>/{window-results.json, window-hits.txt}     # testrun.py (per kind)
```
`window-results.json` is the *summary* (name, status, `issued_in_window`); per-record timing detail and the transmitter `kind` are not retained there. With `_sweep_watcher.py` you must join back to the `.ann.json` to get the kind; `testrun.py` instead partitions into per-`kind` dirs at write time. Re-run the checker with `--out` to recover full per-record timing.

**Streaming asm+gem5.** When a single invocation requests both `asm` and `gem5` (i.e. `all`), `phase_asm_gem5_streaming` interleaves compilation and simulation instead of materializing all asm first. The per-type checker is chosen from each test's `ann["xmit"]["kind"]` via `_KIND_TO_CHECKER`: `ld`→`check_ld.py`, `br_x`→`check_br.py`, `other_x`→`check_other.py` (default `check_ld.py`).

**The sweep watcher (`results/_sweep_watcher.py`).** A *gem5-only* consumer: it polls a testset being compiled by another process, finds `asm ∩ ann` stems not yet in its cumulative results, stages them as symlinks, runs `pipeline.py gem5` on just that batch, and merges into `results/<results_name>/<mode>/window-results.json`. It never compiles. This is how one testset is swept against several builds/schemes concurrently (each watcher gets its own `results/<name>/run_config.jsonc` pointing at a different gem5 binary). Launch pattern:
```bash
nohup python3 -u results/_sweep_watcher.py \
    --config results/<name>/run_config.jsonc --model <testset-model> \
    --interval 300 --max-new 2000 > results/<name>/watcher.log 2>&1 &
```

**Leak criteria (the checkers).** A transmitter "leaks" if its observable action happens inside the speculative window `lc_retire < signal < fnc_retire` while branches are still unresolved.
- `check_ld.py`: `signal` = LSQ "Executing load" tick (cache touch; visible even for squashed speculative loads that never emit pipeview lines). Disqualifies if a specified last-committed predecessor never retires.
- `check_br.py`: branch-redirect detection. Note it does **not** enforce the `lc/fnc` window the way `check_ld` does — a known gap that inflates branch hit rates.

**Bug-diagnosis scripts (per-results, known-vs-new triage).** Each results
folder carries its own `diagnostics/` directory of bug-attribution scripts. The
point is **results-specific bucketing**: once a particular bug/problem/artifact is
known to exist on a particular gem5 build + model, write a script that buckets
exactly that case, so on every future run the records split into **known**
(attributed) vs **new** (unexplained — the fresh research signal). This keeps
re-runs from re-litigating solved cases and surfaces only genuinely novel hit
types. A script takes a record (its `window-results.json` row + the test's
XML / `.ann.json` / pipeview) and returns whether *this* record is explained by
*that* one cause — it encodes the cause's signature, not just "is it a hit."

**Rules (enforce these):**
- **Super specific — one cause per script.** A diagnostic encodes exactly one
  bug/artifact. Don't write a catch-all.
- **Propagate only to the cause's true scope — never beyond it.**
  - A **testset-specific** cause (model-expressivity / concretization artifact tied
    to a particular testset, e.g. the const-addr load artifact in `SPT_6_oneLP`)
    goes **only to runs on that same testset** — *not* to other models/testsets in
    the same name family (e.g. `SPT_6_full` is a different testset → does not get it).
  - A **build-specific** cause (a behavior of one gem5 build) goes to **all runs on
    that build**. (We have none of these yet.)
  - Never blanket-copy across a name family; if it matches 0 in a folder, it doesn't
    belong there.
- **Conservative.** Only bucket a record when **100% certain** it's that cause —
  never hide a record that could be a real leak. Ambiguous → leave it **new**.
- **It may bucket errors, not just hits.** If a known code/build bug (e.g. the
  dup-PC Stage-2 codegen bug) is why a *specific* run errors or drops tests, an
  error-bucketing diagnostic in that run's folder is correct.
- **Every diagnostic script MUST ship with a bug `.md` next to it** (same
  `diagnostics/` dir) that explains: (1) the exact issue it diagnoses and its
  signature, (2) the evidence/root cause, and (3) an explicit verdict on whether it
  is a **real bug** (model-expressivity gap, concretization/codegen bug, gem5
  hook bug, or a real gem5 bug) **or a build/config issue** — so a future session
  knows what the bucket means without re-deriving it.
- Scripts live with the results (not in `STAGE3_gem5/`) because attribution is
  defense/build-specific. A **global checker fix** (e.g. `check_br.py`) or a
  source bug-fix is **not** a diagnostic — it goes in the pipeline; only the
  *bucketing of a known cause's records* is a diagnostic.

## Gotchas

- **Editing `parsexml.py` or a `.als` mid-run contaminates a testset** (some asm uses old logic, some new). Regenerate from the affected stage onward with the relevant stage output wiped.
- Cross-stage invariants and their rationale (e.g. "xmit branches are always resolved in STT_6", and the dormant NOP-insertion bug that depends on it) live in `DESIGN.md` — read it before changing the Alloy speculation contract or `parsexml.py:pass2_5_specify_branches`.
- `AUDIT.md` tracks known issues/findings; `results.md` / `reconresults.md` hold run write-ups.
- `testsets/`, `results/`, `generated/` are gitignored — they're large generated artifacts, not source.
