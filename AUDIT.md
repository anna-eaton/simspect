# SimSpect Audit — Findings

Read-only audit of the SimSpect codebase (Stage 1 Alloy → Stage 2 compilation → Stage 3 gem5), top-level orchestrator, run configs, and gem5 hooks at `/work/stt`, `/work/gem5-recon-modded`, `/work/amulet/amulet-gem5-STT_AE-v1.1`.

## Critical

### 1. `STT_all_amulet` is 100% errors, watcher reports it as "0 hits"
- `results/STT_all_amulet/mispredict_not_taken/window-results.json` — 41,373 records, **every single one** `status="error"`, `xmit_kind=None`, `issued_in_window=False`.
- Underlying error (visible in `sweep/raw_results/*.json`):
  `fatal: Port <orphan System>.cpu.icache_port is already connected to <orphan System>.cpu.icache.cpu_side`.
- Cause: the amulet binary (`/work/amulet/amulet-gem5-STT_AE-v1.1`) is a **Ruby-only build** (`PROTOCOL=MESI_Two_Level`). Its `configs/example/se.py:325` already wires `cpu.icache_port = ruby_port.slave`. The run config passes `"caches": true`, which makes `se.py` *also* call `CacheConfig.config_cache(...)` → connects classic caches over the same port → fatal.
- `watcher.log` quietly logs `+522 → cumulative 41373 tests, 0 hits` — reads like "defense works." It does not. The amulet track has produced **zero valid data points**, but is still running (pid 12028).

**Fix:** stop the watcher, set `caches: false` in `results/STT_all_amulet/run_config.jsonc`, discard the existing `window-results.json` before resuming.

### 2. `STT_6.als`, `STT_6_interleave.als`, `STT_all.als` are byte-identical — RESOLVED
`STT_6_interleave.als` and `STT_all.als` are symlinks to `STT_6.als` (since 2026-05-21). md5sum dereferences symlinks, so the original "identical hashes" observation reflects a single source of truth, not duplicated content. The "variants" still differ only in the run-config `interleave` block (STT_6: disabled; STT_6_interleave: 4 variants; STT_all: 8 variants) — that is the intended design. No further action; symlinks kept so existing `--model STT_6_interleave` / `--model STT_all` launchers keep distinct testset/results dirs.

## Inconsistencies / dead config

### 3. `run_config_STT_6.jsonc` `interleave.chain.types: ["reg","addr","mem"]` is dead — RESOLVED
Trimmed the dead interleave block in `run_config_STT_6.jsonc` down to `{"enabled": false}`. Interleave variants live in their own configs (`run_config_STT_6_interleave.jsonc`, `run_config_STT_all.jsonc`).

### 4. `parsexml.py:600-603` `pass2_specify_instructions` raises `NotImplementedError` for `additional_interleave > 0` — RESOLVED
Removed the `additional_interleave` parameter, the `NotImplementedError` branch, and the stub comment. Real interleaving lives in `pass_interleave`. Only caller (`batch_generate.py:101`) never passed the kwarg.

### 5. `pipeline.py:308-312` `_LEGACY_SCRIPTS` references `pipeline_window.py` — RESOLVED
Ripped out the legacy mode entirely. `_LEGACY_SCRIPTS`, `check_mode`, and the legacy branches at the streaming + non-streaming gem5 paths are gone; only per-type dispatch remains. Removed the unused `STAGE3_gem5/pipeline.py` and `STAGE3_gem5/pipeline_window_complete.py` standalone runners (see #10). Trimmed the legacy-mode commentary from `run_config.jsonc`. All shipped run-configs already used `per_type`.

### 6. `pipeline.py:_read_xmit_kind` silently defaults to `"ld"` on any exception (line 322) — RESOLVED
Removed the `except: return "ld"` fallback. The function now raises on missing file, parse error, or missing `xmit.kind`. All five callers let the exception propagate, so an unreadable ann file now crashes the pipeline instead of misrouting the test to `check_ld`.

### 7. `STAGE1_alloy/models/STT_6.als:38` has stray `å` in a comment
`one sig IX0 {} -- spo position 0 (first)å` — harmless to Alloy parser but suggests an editor accident. Same byte sequence in interleave.als / STT_all.als (because they're the same file).

### 8. `STT_6.als` lines 41-43 comments are wrong
```
one sig IX3 {} -- spo position 2   ← should be 3
one sig IX4 {} -- spo position 2   ← should be 4
one sig IX5 {} -- spo position 2   ← should be 5
```

## Dead / duplicate code

### 9. `STAGE3_gem5/check_ld.py` and `check_other.py` are functionally identical
Only the description string and function name differ. The kind→checker map in `pipeline.py:298` routes `ld` → `check_ld.py` and `other_x` → `check_other.py`, but the resulting computation is identical. Either consolidate into one script or differentiate (e.g. `other_x` should have a different window check if its leak mechanism really is "timing at complete" vs cache state at complete).

### 10. `STAGE3_gem5/pipeline.py` (333 lines) and `pipeline_window_complete.py` (310 lines) — RESOLVED
Both deleted alongside the legacy-mode removal in #5. Per-type dispatch is the only path now.

### 11. `STAGE3_gem5/run.py`, `run_s.py`, `check_speculative.py`, `gen_hits_overview.py` — RESOLVED
All four moved to `STAGE3_gem5/old_scripts/`. None were referenced from the active pipeline (`run_s.py` was only invoked by `verify_resolution_strict.py`, which is itself retired under #13). The `inst-000003` / `IX0..IX3` hardcoding makes them unsafe to re-enable without rework.

### 12. `parsexml.py:1072 _VPOOL_IDX_SCRATCH = 0` reserved but never used
Comment honestly admits it's only there "to preserve register-layout stability across the cond_reg/probe_base slots." Costs one register for no benefit if you're willing to renumber.

### 13. Top-level analysis scripts that look like prior iterations — RESOLVED
Moved to `old_scripts/`: `analyze_hits.py`, `analyze_ld_timing.py`, `analyze_ld_window_timing2.py`, `analyze_results.py`, `analyze_xml.py`, `investigate_br_hits.py`, `verify_resolution_strict.py`, `verify_unresolved_at_xmit.py`, `why_failing.py`, `plot_sweep.py`, `scan_otb_shape.py`. None were referenced from active pipeline code. `categorize_hits.py` kept at the top level (still load-bearing).

## Latent bugs

### 14. `parsexml.py:817-847` NOP-after-xm-branch can create duplicate PCs — DOCUMENTED (dormant)
Verified bug, but unreachable under STT_6's Alloy constraints. The NOP-insertion path only runs for *unresolved* xm branches; empirical scan of 30,000 STT_6 instances shows every xm `br_x` is resolved (9,995 / 9,995). So the duplicate-PC case never fires. The misleading "Not needed" comment in `pass2_5_specify_branches` has been rewritten to explain the dependency, and `DESIGN.md` documents the invariant ("xmit branches are always resolved") along with the empirical evidence and the remediation path if a future model breaks it.

### 15. `parsexml.py:1819,1827,1838` `idivq` codegen with no nonzero guarantee
Confirmed known issue, ~4% of ld tests die with `panic: fault (Divide-Error)`. Suggested fix (`orq $1, divisor`) still not applied.

### 16. `_phase_gem5_sweep` (non-streaming) bails if `window-results.json` exists
`pipeline.py:632`. The streaming path is incremental; the standalone `pipeline.py gem5` invocation is one-shot. Inconsistent ergonomics — if a user runs `pipeline.py gem5` to resume a partially-completed sweep, they're told "pass --force" and `--force` wipes everything. The watcher works around this; CLI users get burned.

### 17. `pipeline.py:910-914` hits-copy loop is O(N²)
```python
batch_hits = [r["name"] for r in existing
              if r.get("issued_in_window")
              and not (hits_dir / (r["name"] + ".s")).exists()]
```
Walks all `existing` results and stats the filesystem on every batch. For 100k tests this is ~5B operations + 100k stats per batch.

### 18. `save_provenance` only archives `parsexml.py`, the `.als`, and the run config
Misses `batch_generate.py`, `compile_annotate.py`, and `instructions.jsonc` — all of which are deterministic pipeline inputs. A future run could load the provenance archive and still get different results.

### 19. `_aggregate_sweep_results` writes per-test sidecars even for non-hit tests
For 100k tests → 100k tiny JSON files in `sweep/`. The data is also already in `window-results.json`. fs overhead is real (~30s just to `ls` the directory).

## Things to verify

### 20. STT_6 result asymmetry
Worth sanity-checking:

| run | not_taken hits | taken hits |
|---|---|---|
| STT_6 (recon) | 825 | 884 |
| STT_6_sttbuild | 1189 | 7135 |
| STT_6_interleave (recon) | 885 | 1221 |
| STT_6_interleave_sttbuild | 1415 | 7068 (still incomplete, 94k/100k) |
| STT_all_recon | 7392 (not_taken only) | — |
| STT_all_sttbuild | 1900 (not_taken only) | — |
| STT_all_amulet | 0 (all errors, see #1) | — |

The 6-7× higher `mispredict_taken` hit rate on the sttbuild track but **not** on recon-modded is striking. Either STT_all has different protection semantics than STT_6 (despite identical `.als` — see #2) or the two gem5 builds disagree on what the taken-mode misprediction window looks like. The fact that STT_all_recon (ostensibly *more* permissive interleave) lands at 7392 — similar to *sttbuild* STT_6 taken — suggests it's a per-build behavior, not a model issue. Worth confirming before publishing numbers.

### 21. `pass_interleave` branch-target remapping vs `ftbypass_<pc>` trampolines
`parsexml.py:1022-1037` only rewrites `bb_X` targets to `bb_<rec.pc+1>` and re-routes `end_block` to the next pc when on the spec path. If a chain step lands between a branch and end_block on a `mispredict_taken` ftbypass trampoline, the trampoline target may now jump to a chain step instead of bypassing it. The `ftbypass_<pc>` label isn't tracked in `new_block_pcs`. Probably fine because the trampoline target is end_block (not `bb_*`), but worth a spot-check on an interleave hit.
