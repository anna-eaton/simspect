# Near-miss breakdown of gem5 campaigns (2026-10-29)

**What this is.** For every gem5 campaign on cafe2 (`/tests/simspect/results/`), each test is classified by which leak criteria it passes or fails, so we can see the "near misses": tests that fail **exactly one** criterion and pass all the others. Raw counts are in [`near_miss_breakdown.json`](near_miss_breakdown.json) (same folder), so the dashboard can read them. The analysis was read-only: python3 was run inside `gem5_dev` on cafe2, it printed JSON to stdout, and nothing was written on cafe2.

> **⚠ Caveat: the gem5-spt and gem5-recon-modded numbers are not comparable to /work/stt.** Every campaign on `/work/gem5-spt` and `/work/gem5-recon-modded` (marked `NO-ANN` below) ran with **no branch annotations loaded in gem5**. Those builds' `se.py` reads only `branch_pc_addr*`, but the pipeline wrote `branch_addr*` (verified 2026-10-29: `config.ini` `annotationBranchPCs` is empty). So gem5 never applied a resolve stall or a BTB force. The checker still evaluates criterion B against the annotation's analytic `stall` (you can see `stall: 5000` in the records' `branch_resolutions`), but the simulated speculative window was the un-stalled one. Their hit and near-miss counts describe a different microarchitectural regime from the `/work/stt` runs. The legacy dirs labelled "recon" (`STT_6/`, `STT_6_interleave/`, `STT_all_recon/`) have no `run_config.jsonc`. `wiki/design/AUDIT.md:96-100` calls them "recon", so they are presumed to fall under the same caveat, but the exact binary is not recorded.

## Headline

- **Most non-hits are not near misses.** In every campaign, the dominant non-hit pattern is `S` or `SL`: the transmitter produced no signal at all (`xmit_signal == 0`: the load never executed in the LSQ, or the branch never broadcast a redirect). When `lc_retire > 0`, a zero signal also fails `after_lc` by construction, so `SL` is really one root cause. "Near-miss with signal present" in the tables excludes every `S`-containing near miss. That is the interesting set.
- **/work/stt (STT_6_sttbuild, STT_6_interleave_sttbuild, stt_coincidence, slow_comm sample_stock): 0 load near-misses with signal present.** Every non-hit load either never executed (`S`) or never executed with lc retired (`SL`). The STT delay holds the load completely. The branch near-misses on /work/stt are all `B`: the redirect fell inside the lc/fnc window, but another annotated branch had already resolved (stt_coincidence STT_6: 198 + 22; STT_6_interleave: 751 + 6; interleave_sttbuild: 2).
- **gem5-recon-modded (STT_6, STT_6_interleave, Recon_6), NO-ANN: the near-misses with signal present are mostly `G`.** These loads executed in-window, but the data-obtained gate rejected them (spec-read-only or delay bounce): STT_6 not_taken 459, taken 2524; STT_6_interleave 546 / 3075; Recon_6 323, plus 306 `F` and 115 `L`.
- **gem5-spt (SPT_6_oneLP_fence, newts), NO-ANN: the near-misses with signal present are mostly `L`.** The signal came before `lc_retire` (oneLP 358 / 375, plus 55 / 76 `D`).
- **Slow-comm experiments have the largest near-miss pools.** `spt_slowcomm_fence` ld: `L` 10382 (not_taken) and `L` 9823 + `F` 3697 (taken). `stt_slowcomm_full` ld: `L` 4867 (not_taken) and 1023 (taken). Under slow commit→IEW, many loads execute just before lc retires or just after fnc retires.
- **The current-checker branch campaigns (br_x kind) have essentially no hits.** Every non-hit is `SR` or `SLR` (no redirect broadcast), except where noted above.
- **The checker's verdict matches the recomputation in at least 99.9% of records on every current-checker campaign (100.0% on all but spt_slowcomm_fence ld, which is 99.9%).** The exceptions are the legacy dirs that used older checker versions (see the method section).

## Method

### Data sources

- **Per-test records.** These come from `window-results.json` where it holds full checker records (the experiments, `SPT_6*` 5000-test dirs, invisispec, speclfb). Where a campaign's `window-results.json` is summary-only (`name, status, issued_in_window, sweep_grid_size, sweep_triggered`, produced by `pipeline.py:_aggregate_sweep_results` at `pipeline.py:499`), the full per-grid-point checker records were read from the campaign's sweep raw dir (`<mode>/_sweep_raw/` for testrun campaigns, `<mode>/sweep/raw_results/` for watcher campaigns, `Recon_6/sweep/raw_results/`). Every summary-only campaign had a raw dir, so **every campaign could be broken down**, with the exceptions listed under "Not broken down". Raw duplicates of the same (test, grid index) keep the newest file by mtime.
- **Sweep → test aggregation.** A test is run at several stall grid points. Mirroring `pipeline.py:533` (`any_hit`), a test is a **hit** if the checker's `issued_in_window` is true at any grid point. A test is an **error** if no grid point returned a non-error record (`status != ok` or `error` set). For non-hit tests, the **joint pattern** reported is the failset at the grid point with the fewest failures. A test is a **near-miss** if any grid point fails exactly one criterion. If different grid points give different single failures, it is listed as `multi:X/Y`.
- **Mode/kind.** Testrun campaigns are split per `<mode>/<kind>/`, and raw records are mapped to a kind by test-name membership. Legacy watcher dirs are mixed-kind (`all`).

### Load criteria (`STAGE3_gem5/check_ld.py`)

Letters are used in the tables:

| letter | criterion | code | recomputed from fields |
|---|---|---|---|
| D | not disqualified | `check_ld.py:98` `lc_unretired_but_specified = lc_pc is not None and lc_retire == 0` | `lc_unretired_but_specified`; only applied when the field exists (checkers before `14fcb1f` had no disqualifier) |
| S | signal > 0 | `check_ld.py:87` `xmit_signal = xmit_execute if >0 else xmit_complete` | `xmit_signal`; fallback `xmit_execute` or `xmit_complete` for old records |
| L | after lc | `check_ld.py:108` `lc_retire == 0 or xmit_signal > lc_retire` | recomputed from `lc_retire`, signal |
| F | before fnc | `check_ld.py:109` `fnc_retire == 0 or xmit_signal < fnc_retire` | recomputed from `fnc_retire`, signal |
| B | other annotated branches still unresolved | `gem5_common.py:708-735` (`xmit < complete + stall*ticks_per_cycle`, or the branch never completed) | stored `branches_unresolved` (needs the trace, so it can't be recomputed) |
| G | data obtained | `check_ld.py:130-146`: gated only when `xmit_execute > 0` and `data_obtained is not None` | fails iff `xmit_execute > 0` and `data_obtained is False`. If the field is absent (checker before `e298a9e`, 2026-06-03), G was not applied and is reported as gate `absent` |

Full pass of D∧S∧L∧F∧B∧G reproduces `issued_in_window` (`check_ld.py:112-146`). G is evaluated independently of the window, so a test can fail only `F` while having `data_obtained = True`.

### Branch criteria (`STAGE3_gem5/check_br.py`, current version)

| letter | criterion | code |
|---|---|---|
| D | not disqualified | `check_br.py:87` |
| S | signal > 0 | `check_br.py:65`: signal is the Commit-trace squash tick (`xmit_redirect`); without a Commit trace it is `xmit_complete` (`:70`) |
| L, F | lc/fnc window on the signal | `check_br.py:90-91` |
| B | other branches unresolved | `check_br.py:93` |
| R | branch_redirected (the fall-through did not retire) | `check_br.py:66-76`. The fall-through retire tick is **not stored**. R counts as a definite fail when S fails, because redirect requires signal > 0. When D/S/L/F/B all pass, R is a definite fail if the test was not issued. Otherwise R is unknown and the pattern is written `+R?` |

So a branch "near-miss" is either exactly-R (never observed) or a single failure among D/L/F/B with R unknown (`X+R?`).

**Legacy branch records.** Records without `xmit_signal` and with `xmit_complete = null` come from the original `last-alive` check_br (git `dd36e15`: `issued = xmit_last_alive > ft_last_alive`). Their recorded verdict also counts equal last-alive ticks as hits, so the original semantics can't be reconstructed from the code in git. These are treated as one opaque criterion `A` = the recorded verdict. Their non-hits appear in the "legacy br opaque non-hits" column and are **excluded** from the near-miss counts. This explains the less-than-100% consistency on the `SPT_6*`, `SPT_6_full*` and `STT_all_*` dirs.

### Other checkers

- `check_other.py:32-37`: S (`xmit_complete > 0`), L, F, B. No disqualifier. **No campaign has `other_x` records**, so nothing was reported.
- `check_footprint.py`: D (`:201`), then a per-criterion footprint-in-window evaluation from `specs/leakage/<defense>.json` (`:242-255`). **No campaign has results yet.** `STT_6_cleanupspec_full`, `STT_6_invisispec_full_futuristic`, `STT_6_invisispec_full_spectre` and `STT_6_speclfb_full` contain only a README and `run_config.jsonc`.
- `check_ld_invisispec.py:87-96`: D, S (`expose_tick > 0`), L, F, B on `expose_tick`.
- `check_ld_speclfb.py:88-103`: D, S (`cache_fill_tick > 0`), L, F, B on the fill tick, plus U (`spec_unprotected`).
- `check_ld_invisispec_compound.py` (`forbidden`, ...): counted for totals and hits only, not decomposed.
- `div_fault` hits promoted by `gem5_common.py:classify_divide_panic` would be their own bucket (none found).

### Excluded as superseded

These were not analysed: `_archive_SPT_6_oneLP_20260601_201714`, `prebranchfixResults`, `*_WRONG_REGIME_*`, `_tmp_*`, all `*__latest` symlinks (duplicates of the timestamped dir), and `STT_6_cleanupspec_residue` (no `window-results.json`, only `window-results_on*.json` demos).

### Not broken down

- `STT_6_invisispec_compound` (both modes): compound checker, totals only.
- `_verify_ld_taken`: all 1270 records are hits, from a checker version before the G gate, and there is no config in the dir.

## Builds per campaign

| campaign | gem5 binary | variant | provenance |
|---|---|---|---|
| `Recon_6`, `Recon_6__20260602_122016` | `/work/gem5-recon-modded/build/X86/gem5.opt` (NO-ANN) | scheme 2 | `Recon_6/run_config.jsonc`, manifest |
| `STT_6__20260602_015852`, `STT_6_interleave__20260602_015852` | `/work/gem5-recon-modded` (NO-ANN) | scheme 2 | manifest.json |
| `STT_6/`, `STT_6_interleave/`, `STT_all_recon` (legacy watcher) | "recon", exact binary unrecorded (presumed NO-ANN) | scheme 2 | `wiki/design/AUDIT.md:96-100` |
| `STT_6_sttbuild__20260602_013615`, `STT_6_interleave_sttbuild__20260602_013615`, `STT_all_sttbuild` | `/work/stt/build/X86/gem5.opt` | scheme 2 | run_config + manifest |
| `STT_all_amulet` | `/work/amulet/amulet-gem5-STT_AE-v1.1` | scheme 2 | run_config |
| `SPT_6_full_fence`, `SPT_6_oneLP_fence__*`, `SPT_6_oneLP_fence_newts__*` | `/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt` (NO-ANN) | SpectreSafeFence (full: Ignore; oneLP: Lazy; `__20260610`: freeParam=3) | run_config / manifest |
| `SPT_6_full_invispec` | `/work/gem5-spt` (NO-ANN) | SpectreSafeInvisibleSpec, Ignore | run_config |
| `SPT_6`, `SPT_6_FuturisticFence`, `SPT_6_FuturisticInvisibleSpec`, `SPT_6_SpectreInvisibleSpec`, `SPT_6_disableUntaint`, `SPT_6_full` | `/work/gem5-spt`, inferred from name (no run_config in dir) | per dir name | none |
| `STT_6_invisispec`, `STT_6_invisispec_compound` | `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1` | SpectreSafeInvisibleSpec | run_config / `run_invisispec_compound.py:25` |
| `STT_6_speclfb` | `/work/amulet/amulet-gem5-SpecLFB_AE-v1.1` | SpecLFB | `run_speclfb.py:29` |
| `experiments/paper_stalls/{sU,sR,fnc}_*` | `/work/gem5-recon-modded` (NO-ANN) | scheme 2 | `stall_sweep.sh` → `paper_stalls/STT_6_run_config.jsonc:25` |
| `experiments/paper_stalls/stt_*` | `/work/stt` | se_exp.py slow-comm (commitToIEWDelay=3) | `stall_sweep_stt.sh` |
| `experiments/paper_fragility/frag_d*` | `/work/stt` | commitToIEWDelay = d | `frag_sweep.sh` |
| `experiments/paper_fragility/fence_d*` | `/work/gem5-spt` (NO-ANN) | SpectreSafeFence, commitToIEWDelay = d | `fence_sweep.sh` |
| `experiments/slow_comm_squash1/{sample,sample_stock}` | `/work/stt` | slow-comm / stock | run_config, `stock_run_config.jsonc:34` |
| `experiments/spt_slowcomm_fence__20260602_121858` | `/work/gem5-spt` (NO-ANN) | SpectreSafeFence, Lazy, slow-comm | manifest |
| `experiments/stt_slowcomm_full__20260602_121858` | `/work/stt` | slow-comm | manifest |
| `experiments/stt_coincidence/*__20260602_122722` | `/work/stt` | scheme 2, stall grid (max 24 points) | manifest + run_config |

## How to read the tables

- `tests` is the number of tests in the summary `window-results.json`.
- `errors` counts tests with no usable record.
- `hits` uses the checker's own verdict (any grid point).
- `near-miss by criterion` gives counts per single failing letter.
- `near-miss with signal present` is the same set with every `S`-containing entry removed.
- The joint pattern is the failset at each non-hit test's best grid point. `PASS(recomputed)` means a non-hit whose fields recompute to a pass, which only happens with legacy checkers.
- The last column gives: the fraction of grid-point records whose recomputed verdict equals the recorded `issued_in_window`; the checker families seen (`ld`, `br` = current, `br_v0` = legacy last-alive, `ld_invisispec`, `ld_speclfb`); and how G was evaluated (`direct` = field present, `absent` = pre-gate checker, `residual` = branch R).

## Current-checker campaigns (testrun `__<ts>` dirs)

| campaign / mode / kind | gem5 binary | ann caveat | tests | errors | hits | non-hits | near-miss (exactly 1 fail) | near-miss by criterion | near-miss with signal present | legacy br opaque non-hits | joint pass/fail pattern at best grid point (top 5) | records consistent w/ recorded verdict; checker families; gate eval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `Recon_6__20260602_122016/mispredict_not_taken/br_x` | gem5-recon-modded | NO-ANN | 51703 | 0 | 0 | 51703 | 0 | - | 0 | - | SLR:31198, SR:20488, DSR:17 | 100.0%; br; gate residual |
| `Recon_6__20260602_122016/mispredict_not_taken/ld` | gem5-recon-modded | NO-ANN | 48297 | 0 | 184 | 48113 | 19974 | S:19230, G:323, F:306, L:115 | 744 | - | SL:27257, S:19230, FG:584, G:323, F:306, ...(+3) | 100.0%; ld; gate absent,direct |
| `SPT_6_oneLP_fence__20260602_013615/mispredict_not_taken/br_x` | gem5-spt | NO-ANN | 3126 | 0 | 0 | 3126 | 0 | - | 0 | - | SLR:2309, SR:763, DSR:54 | 100.0%; br; gate residual |
| `SPT_6_oneLP_fence__20260602_013615/mispredict_not_taken/ld` | gem5-spt | NO-ANN | 14874 | 0 | 2994 | 11880 | 3448 | S:3035, L:358, D:55 | 413 | - | SL:8247, S:3035, L:358, DS:185, D:55 | 100.0%; ld; gate absent |
| `SPT_6_oneLP_fence__20260602_013615/mispredict_taken/br_x` | gem5-spt | NO-ANN | 3126 | 0 | 0 | 3126 | 0 | - | 0 | - | SLR:2309, SR:763, DSR:54 | 100.0%; br; gate residual |
| `SPT_6_oneLP_fence__20260602_013615/mispredict_taken/ld` | gem5-spt | NO-ANN | 14874 | 0 | 3124 | 11750 | 3437 | S:2986, L:375, D:76 | 451 | - | SL:8149, S:2986, L:375, DS:164, D:76 | 100.0%; ld; gate absent |
| `SPT_6_oneLP_fence__20260610_112453/mispredict_not_taken/br_x` | gem5-spt | NO-ANN | 146 | 0 | 0 | 146 | 0 | - | 0 | - | SLR:111, SR:35 | 100.0%; br; gate residual |
| `SPT_6_oneLP_fence__20260610_112453/mispredict_not_taken/ld` | gem5-spt | NO-ANN | 1354 | 0 | 494 | 860 | 201 | S:172, L:25, G:4 | 29 | - | SL:659, S:172, L:25, G:4 | 100.0%; ld; gate direct |
| `SPT_6_oneLP_fence__20260610_112453/mispredict_taken/br_x` | gem5-spt | NO-ANN | 146 | 0 | 0 | 146 | 0 | - | 0 | - | SLR:111, SR:35 | 100.0%; br; gate residual |
| `SPT_6_oneLP_fence__20260610_112453/mispredict_taken/ld` | gem5-spt | NO-ANN | 1354 | 0 | 553 | 801 | 188 | S:160, L:17, G:11 | 28 | - | SL:613, S:160, L:17, G:11 | 100.0%; ld; gate direct |
| `SPT_6_oneLP_fence_newts__20260610_114140/mispredict_not_taken/br_x` | gem5-spt | NO-ANN | 504 | 0 | 8 | 496 | 4 | L:4 | 4 | - | SLR:472, DSR:16, SR:4, L+R?:4 | 100.0%; br; gate residual |
| `SPT_6_oneLP_fence_newts__20260610_114140/mispredict_not_taken/ld` | gem5-spt | NO-ANN | 492 | 0 | 11 | 481 | 10 | S:8, L:2 | 2 | - | SL:456, DS:15, S:8, L:2 | 100.0%; ld; gate direct |
| `SPT_6_oneLP_fence_newts__20260610_114140/mispredict_not_taken/str` | gem5-spt | NO-ANN | 504 | 0 | 11 | 493 | 13 | S:8, L:5 | 5 | - | SL:464, DS:16, S:8, L:5 | 100.0%; ld; gate direct |
| `SPT_6_oneLP_fence_newts__20260610_114140/mispredict_taken/br_x` | gem5-spt | NO-ANN | 504 | 0 | 0 | 504 | 0 | - | 0 | - | SLR:480, DSR:16, SR:8 | 100.0%; br; gate residual |
| `SPT_6_oneLP_fence_newts__20260610_114140/mispredict_taken/ld` | gem5-spt | NO-ANN | 492 | 0 | 14 | 478 | 10 | S:8, L:2 | 2 | - | SL:453, DS:13, S:8, L:2, DG:2 | 100.0%; ld; gate direct |
| `SPT_6_oneLP_fence_newts__20260610_114140/mispredict_taken/str` | gem5-spt | NO-ANN | 504 | 0 | 13 | 491 | 12 | S:8, L:4 | 4 | - | SL:463, DS:16, S:8, L:4 | 100.0%; ld; gate direct |
| `STT_6__20260602_015852/mispredict_not_taken/br_x` | gem5-recon-modded | NO-ANN | 27389 | 0 | 0 | 27389 | 0 | - | 0 | - | SLR:20805, SR:6584 | 100.0%; br; gate residual |
| `STT_6__20260602_015852/mispredict_not_taken/ld` | gem5-recon-modded | NO-ANN | 66512 | 0 | 253 | 66259 | 20246 | S:19773, G:459, L:14 | 473 | - | SL:45996, S:19773, G:459, LG:17, L:14 | 100.0%; ld; gate direct,absent |
| `STT_6__20260602_015852/mispredict_taken/br_x` | gem5-recon-modded | NO-ANN | 27389 | 0 | 0 | 27389 | 0 | - | 0 | - | SLR:20805, SR:6584 | 100.0%; br; gate residual |
| `STT_6__20260602_015852/mispredict_taken/ld` | gem5-recon-modded | NO-ANN | 66512 | 0 | 717 | 65795 | 21832 | S:19263, G:2524, L:45 | 2569 | - | SL:43955, S:19263, G:2524, L:45, LG:8 | 100.0%; ld; gate direct,absent |
| `STT_6_interleave__20260602_015852/mispredict_not_taken/br_x` | gem5-recon-modded | NO-ANN | 133952 | 0 | 0 | 133952 | 0 | - | 0 | - | SLR:93672, SR:40280 | 100.0%; br; gate residual |
| `STT_6_interleave__20260602_015852/mispredict_not_taken/ld` | gem5-recon-modded | NO-ANN | 266048 | 0 | 89 | 265959 | 80307 | S:79757, G:546, L:4 | 550 | - | SL:185629, S:79757, G:546, LG:23, L:4 | 100.0%; ld; gate direct,absent |
| `STT_6_interleave__20260602_015852/mispredict_taken/br_x` | gem5-recon-modded | NO-ANN | 109592 | 0 | 0 | 109592 | 0 | - | 0 | - | SLR:82804, SR:26788 | 100.0%; br; gate residual |
| `STT_6_interleave__20260602_015852/mispredict_taken/ld` | gem5-recon-modded | NO-ANN | 217408 | 0 | 512 | 216896 | 56083 | S:52994, G:3075, L:14 | 3089 | - | SL:160773, S:52994, G:3075, LG:40, L:14 | 100.0%; ld; gate direct,absent |
| `STT_6_interleave_sttbuild__20260602_013615/mispredict_not_taken/br_x` | stt |  | 6044 | 0 | 0 | 6044 | 2 | B:2 | 2 | - | SR:3256, SLR:2751, FB+R?:30, DSR:5, B+R?:2 | 100.0%; br; gate residual |
| `STT_6_interleave_sttbuild__20260602_013615/mispredict_not_taken/ld` | stt |  | 11956 | 0 | 0 | 11956 | 6496 | S:6496 | 0 | - | S:6496, SL:5460 | 100.0%; ld; gate absent |
| `STT_6_interleave_sttbuild__20260602_013615/mispredict_taken/br_x` | stt |  | 5368 | 0 | 0 | 5368 | 0 | - | 0 | - | SLR:2707, SR:2656, DSR:5 | 100.0%; br; gate residual |
| `STT_6_interleave_sttbuild__20260602_013615/mispredict_taken/ld` | stt |  | 10632 | 0 | 0 | 10632 | 5284 | S:5284 | 0 | - | SL:5348, S:5284 | 100.0%; ld; gate absent |
| `STT_6_sttbuild__20260602_013615/mispredict_not_taken/br_x` | stt |  | 4348 | 0 | 0 | 4348 | 0 | - | 0 | - | SR:2363, SLR:1985 | 100.0%; br; gate residual |
| `STT_6_sttbuild__20260602_013615/mispredict_not_taken/ld` | stt |  | 11652 | 0 | 0 | 11652 | 6447 | S:6447 | 0 | - | S:6447, SL:5205 | 100.0%; ld; gate absent |
| `STT_6_sttbuild__20260602_013615/mispredict_taken/br_x` | stt |  | 4348 | 0 | 0 | 4348 | 0 | - | 0 | - | SR:2363, SLR:1985 | 100.0%; br; gate residual |
| `STT_6_sttbuild__20260602_013615/mispredict_taken/ld` | stt |  | 11652 | 0 | 0 | 11652 | 6447 | S:6447 | 0 | - | S:6447, SL:5205 | 100.0%; ld; gate absent |

## Experiments

| campaign / mode / kind | gem5 binary | ann caveat | tests | errors | hits | non-hits | near-miss (exactly 1 fail) | near-miss by criterion | near-miss with signal present | legacy br opaque non-hits | joint pass/fail pattern at best grid point (top 5) | records consistent w/ recorded verdict; checker families; gate eval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `experiments/paper_fragility/fence_d1/mispredict_not_taken` | gem5-spt | NO-ANN | 150 | 0 | 55 | 95 | 28 | S:21, L:4, G:3 | 7 | - | SL:66, S:21, L:4, G:3, DS:1 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/fence_d1/mispredict_taken` | gem5-spt | NO-ANN | 150 | 0 | 53 | 97 | 21 | S:17, G:3, D:1 | 4 | - | SL:76, S:17, G:3, D:1 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/fence_d2/mispredict_not_taken` | gem5-spt | NO-ANN | 150 | 0 | 61 | 89 | 24 | S:19, L:5 | 5 | - | SL:64, S:19, L:5, DS:1 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/fence_d2/mispredict_taken` | gem5-spt | NO-ANN | 150 | 0 | 62 | 88 | 21 | S:17, L:2, G:1, D:1 | 4 | - | SL:67, S:17, L:2, G:1, D:1 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/fence_d3/mispredict_not_taken` | gem5-spt | NO-ANN | 150 | 22 | 47 | 81 | 22 | S:17, L:5 | 5 | - | SL:58, S:17, L:5, DS:1 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/fence_d3/mispredict_taken` | gem5-spt | NO-ANN | 150 | 21 | 51 | 78 | 16 | S:12, L:2, G:1, D:1 | 4 | - | SL:62, S:12, L:2, G:1, D:1 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/fence_d4/mispredict_not_taken` | gem5-spt | NO-ANN | 150 | 18 | 51 | 81 | 24 | S:17, L:5, G:2 | 7 | - | SL:56, S:17, L:5, G:2, DS:1 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/fence_d4/mispredict_taken` | gem5-spt | NO-ANN | 150 | 16 | 55 | 79 | 17 | S:12, L:2, G:2, D:1 | 5 | - | SL:62, S:12, L:2, G:2, D:1 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/frag_d1/mispredict_not_taken` | stt |  | 300 | 0 | 0 | 300 | 91 | S:91 | 0 | - | SL:209, S:91 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/frag_d1/mispredict_taken` | stt |  | 300 | 0 | 0 | 300 | 96 | S:96 | 0 | - | SL:204, S:96 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/frag_d2/mispredict_not_taken` | stt |  | 300 | 0 | 20 | 280 | 84 | S:82, L:2 | 2 | - | SL:196, S:82, L:2 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/frag_d2/mispredict_taken` | stt |  | 300 | 0 | 0 | 300 | 96 | S:96 | 0 | - | SL:204, S:96 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/frag_d3/mispredict_not_taken` | stt |  | 300 | 0 | 41 | 259 | 78 | S:76, L:2 | 2 | - | SL:181, S:76, L:2 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/frag_d3/mispredict_taken` | stt |  | 300 | 0 | 2 | 298 | 95 | S:95 | 0 | - | SL:203, S:95 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/frag_d4/mispredict_not_taken` | stt |  | 300 | 0 | 42 | 258 | 78 | S:76, L:2 | 2 | - | SL:180, S:76, L:2 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/frag_d4/mispredict_taken` | stt |  | 300 | 1 | 2 | 297 | 95 | S:95 | 0 | - | SL:202, S:95 | 100.0%; ld; gate direct |
| `experiments/paper_fragility/smoke_d4/mispredict_not_taken` | ? |  | 3 | 0 | 0 | 3 | 1 | S:1 | 0 | - | SL:2, S:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/fnc_0/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 48 | S:48 | 0 | - | SL:101, S:48, FG:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/fnc_0/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 37 | S:37 | 0 | - | SL:108, S:37, FG:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/fnc_150/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/fnc_150/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/fnc_300/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/fnc_300/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sR_0/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sR_0/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sR_64/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sR_64/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sR_8/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sR_8/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_0/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_0/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_1000/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_1000/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_250/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_250/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_50/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_50/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_5000/mispredict_not_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 49 | S:48, G:1 | 1 | - | SL:101, S:48, G:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/sU_5000/mispredict_taken` | gem5-recon-modded | NO-ANN | 150 | 0 | 0 | 150 | 42 | S:37, G:5 | 5 | - | SL:108, S:37, G:5 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_fnc_0/mispredict_not_taken` | stt |  | 200 | 0 | 16 | 184 | 65 | S:52, F:11, L:2 | 13 | - | SL:119, S:52, F:11, L:2 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_fnc_0/mispredict_taken` | stt |  | 200 | 0 | 1 | 199 | 57 | S:56, F:1 | 1 | - | SL:142, S:56, F:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_fnc_150/mispredict_not_taken` | stt |  | 200 | 0 | 27 | 173 | 54 | S:52, L:2 | 2 | - | SL:119, S:52, L:2 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_fnc_150/mispredict_taken` | stt |  | 200 | 0 | 2 | 198 | 56 | S:56 | 0 | - | SL:142, S:56 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_fnc_300/mispredict_not_taken` | stt |  | 200 | 0 | 27 | 173 | 54 | S:52, L:2 | 2 | - | SL:119, S:52, L:2 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_fnc_300/mispredict_taken` | stt |  | 200 | 0 | 2 | 198 | 56 | S:56 | 0 | - | SL:142, S:56 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sR_0/mispredict_not_taken` | stt |  | 200 | 0 | 27 | 173 | 54 | S:52, L:2 | 2 | - | SL:119, S:52, L:2 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sR_0/mispredict_taken` | stt |  | 200 | 0 | 2 | 198 | 56 | S:56 | 0 | - | SL:142, S:56 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sR_64/mispredict_not_taken` | stt |  | 200 | 0 | 22 | 178 | 54 | S:54 | 0 | - | SL:124, S:54 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sR_64/mispredict_taken` | stt |  | 200 | 0 | 2 | 198 | 56 | S:56 | 0 | - | SL:142, S:56 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sR_8/mispredict_not_taken` | stt |  | 200 | 0 | 22 | 178 | 54 | S:54 | 0 | - | SL:124, S:54 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sR_8/mispredict_taken` | stt |  | 200 | 0 | 2 | 198 | 56 | S:56 | 0 | - | SL:142, S:56 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_0/mispredict_not_taken` | stt |  | 200 | 0 | 27 | 173 | 54 | S:52, L:2 | 2 | - | SL:119, S:52, L:2 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_0/mispredict_taken` | stt |  | 200 | 0 | 2 | 198 | 56 | S:56 | 0 | - | SL:142, S:56 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_1000/mispredict_not_taken` | stt |  | 200 | 0 | 0 | 200 | 26 | B:26 | 26 | - | FB:171, B:26, FBG:2, BG:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_1000/mispredict_taken` | stt |  | 200 | 0 | 0 | 200 | 48 | S:38, B:10 | 10 | - | SL:95, FB:54, S:38, B:10, FBG:3 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_250/mispredict_not_taken` | stt |  | 200 | 0 | 0 | 200 | 29 | B:29 | 29 | - | FB:168, B:29, FBG:2, BG:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_250/mispredict_taken` | stt |  | 200 | 0 | 0 | 200 | 51 | S:38, B:13 | 13 | - | SL:95, FB:51, S:38, B:13, FBG:3 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_50/mispredict_not_taken` | stt |  | 200 | 0 | 0 | 200 | 93 | B:51, S:42 | 51 | - | SL:103, B:51, S:42, FB:4 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_50/mispredict_taken` | stt |  | 200 | 1 | 0 | 199 | 68 | S:46, B:22 | 22 | - | SL:131, S:46, B:22 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_5000/mispredict_not_taken` | stt |  | 200 | 0 | 0 | 200 | 26 | B:26 | 26 | - | FB:171, B:26, FBG:2, BG:1 | 100.0%; ld; gate direct |
| `experiments/paper_stalls/stt_sU_5000/mispredict_taken` | stt |  | 200 | 0 | 0 | 200 | 48 | S:38, B:10 | 10 | - | SL:95, FB:54, S:38, B:10, FBG:3 | 100.0%; ld; gate direct |
| `experiments/slow_comm_squash1/sample/mispredict_not_taken` | stt |  | 600 | 0 | 187 | 413 | 135 | S:96, L:39 | 39 | - | SL:278, S:96, L:39 | 100.0%; ld; gate absent |
| `experiments/slow_comm_squash1/sample/mispredict_taken` | stt |  | 600 | 0 | 44 | 556 | 183 | S:173, L:10 | 10 | - | SL:373, S:173, L:10 | 100.0%; ld; gate absent |
| `experiments/slow_comm_squash1/sample_stock/mispredict_not_taken` | stt |  | 600 | 0 | 0 | 600 | 172 | S:172 | 0 | - | SL:428, S:172 | 100.0%; ld; gate absent |
| `experiments/slow_comm_squash1/sample_stock/mispredict_taken` | stt |  | 600 | 0 | 0 | 600 | 186 | S:186 | 0 | - | SL:414, S:186 | 100.0%; ld; gate absent |
| `experiments/spt_slowcomm_fence__20260602_121858/mispredict_not_taken/br_x` | gem5-spt | NO-ANN | 12694 | 335 | 669 | 11690 | 794 | L:777, D:17 | 794 | - | SLR:7931, SR:2762, L+R?:777, DSR:203, D+R?:17 | 100.0%; br; gate residual |
| `experiments/spt_slowcomm_fence__20260602_121858/mispredict_not_taken/ld` | gem5-spt | NO-ANN | 84249 | 22 | 40768 | 43459 | 18954 | L:10382, S:7951, D:595, G:23, F:3 | 11003 | - | SL:24078, L:10382, S:7951, D:595, DS:330, ...(+3) | 99.9%; ld; gate absent,direct |
| `experiments/spt_slowcomm_fence__20260602_121858/mispredict_taken/br_x` | gem5-spt | NO-ANN | 11742 | 272 | 8 | 11462 | 7 | L:7 | 7 | - | SLR:8223, SR:3039, DSR:193, L+R?:7 | 100.0%; br; gate residual |
| `experiments/spt_slowcomm_fence__20260602_121858/mispredict_taken/ld` | gem5-spt | NO-ANN | 84249 | 446 | 36787 | 47016 | 21872 | L:9823, S:7686, F:3697, D:639, G:27 | 14186 | - | SL:24857, L:9823, S:7686, F:3697, D:639, ...(+3) | 100.0%; ld; gate absent,direct |
| `experiments/stt_coincidence/STT_6__20260602_122722/mispredict_not_taken/br_x` | stt |  | 27389 | 0 | 0 | 27389 | 198 | B:198 | 198 | - | SLR:20805, SR:6386, B+R?:198 | 100.0%; br; gate residual |
| `experiments/stt_coincidence/STT_6__20260602_122722/mispredict_not_taken/ld` | stt |  | 66512 | 0 | 0 | 66512 | 20006 | S:20006 | 0 | - | SL:46506, S:20006 | 100.0%; ld; gate direct,absent |
| `experiments/stt_coincidence/STT_6__20260602_122722/mispredict_taken/br_x` | stt |  | 27389 | 0 | 0 | 27389 | 22 | B:22 | 22 | - | SLR:20805, SR:6562, B+R?:22 | 100.0%; br; gate residual |
| `experiments/stt_coincidence/STT_6__20260602_122722/mispredict_taken/ld` | stt |  | 66512 | 0 | 0 | 66512 | 20006 | S:20006 | 0 | - | SL:46506, S:20006 | 100.0%; ld; gate direct,absent |
| `experiments/stt_coincidence/STT_6_interleave__20260602_122722/mispredict_not_taken/br_x` | stt |  | 27704 | 0 | 0 | 27704 | 751 | B:751 | 751 | - | SR:15517, SLR:11377, B+R?:751, FB+R?:45, DSR:14 | 100.0%; br; gate residual |
| `experiments/stt_coincidence/STT_6_interleave__20260602_122722/mispredict_not_taken/ld` | stt |  | 51696 | 0 | 0 | 51696 | 28748 | S:28748 | 0 | - | S:28748, SL:22948 | 100.0%; ld; gate direct,absent |
| `experiments/stt_coincidence/STT_6_interleave__20260602_122722/mispredict_taken/br_x` | stt |  | 27704 | 0 | 0 | 27704 | 6 | B:6 | 6 | - | SR:16215, SLR:11430, DSR:52, B+R?:6, LB+R?:1 | 100.0%; br; gate residual |
| `experiments/stt_coincidence/STT_6_interleave__20260602_122722/mispredict_taken/ld` | stt |  | 51696 | 0 | 0 | 51696 | 28748 | S:28748 | 0 | - | S:28748, SL:22948 | 100.0%; ld; gate direct,absent |
| `experiments/stt_slowcomm_full__20260602_121858/mispredict_not_taken/br_x` | stt |  | 27389 | 107 | 198 | 27084 | 0 | - | 0 | - | SLR:20744, SR:6340 | 100.0%; br; gate residual |
| `experiments/stt_slowcomm_full__20260602_121858/mispredict_not_taken/ld` | stt |  | 66512 | 0 | 20295 | 46217 | 16556 | S:11689, L:4867 | 4867 | - | SL:29657, S:11689, L:4867, LG:4 | 100.0%; ld; gate absent,direct |
| `experiments/stt_slowcomm_full__20260602_121858/mispredict_taken/br_x` | stt |  | 27389 | 559 | 33 | 26797 | 0 | - | 0 | - | SLR:20492, SR:6305 | 100.0%; br; gate residual |
| `experiments/stt_slowcomm_full__20260602_121858/mispredict_taken/ld` | stt |  | 66512 | 12 | 3693 | 62807 | 19916 | S:18866, L:1023, G:27 | 1050 | - | SL:42870, S:18866, L:1023, G:27, LG:21 | 100.0%; ld; gate absent,direct |

## Legacy watcher campaigns (older and mixed checker versions)

These dirs predate testrun. Their raw records mix checker versions: pre-disqualifier and pre-gate check_ld, and the legacy last-alive check_br. The `STT_6/`, `STT_6_interleave/` and `Recon_6/results` error counts (about 37-44% of tests) are recorded checker errors, not analysis failures.

| campaign / mode / kind | gem5 binary | ann caveat | tests | errors | hits | non-hits | near-miss (exactly 1 fail) | near-miss by criterion | near-miss with signal present | legacy br opaque non-hits | joint pass/fail pattern at best grid point (top 5) | records consistent w/ recorded verdict; checker families; gate eval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `Recon_6/results` | gem5-recon-modded | NO-ANN | 100000 | 37227 | 848 | 61925 | 14761 | S:13758, F:706, L:297 | 1003 | 32388 | A:32388, SL:14776, S:13758, F:706, L:297 | 100.0%; ld,br_v0,br; gate na,absent |
| `SPT_6/mispredict_not_taken` | gem5-spt (inferred from name; no run_config in dir) | NO-ANN | 5000 | 0 | 726 | 4274 | 914 | S:912, L:2 | 2 | 1825 | A:1825, SL:1535, S:912, L:2 | 91.3%; br_v0,ld; gate na,absent |
| `SPT_6_FuturisticFence/mispredict_not_taken` | gem5-spt (inferred from name; no run_config in dir) | NO-ANN | 5000 | 0 | 697 | 4303 | 918 | S:915, L:3 | 3 | 1851 | A:1851, SL:1534, S:915, L:3 | 91.5%; br_v0,ld; gate na,absent |
| `SPT_6_FuturisticInvisibleSpec/mispredict_not_taken` | gem5-spt (inferred from name; no run_config in dir) | NO-ANN | 5000 | 0 | 1088 | 3912 | 900 | S:761, L:139 | 139 | 1851 | A:1851, SL:1161, S:761, L:139 | 91.5%; br_v0,ld; gate na,absent |
| `SPT_6_SpectreInvisibleSpec/mispredict_not_taken` | gem5-spt (inferred from name; no run_config in dir) | NO-ANN | 5000 | 0 | 1088 | 3912 | 900 | S:761, L:139 | 139 | 1851 | A:1851, SL:1161, S:761, L:139 | 91.5%; br_v0,ld; gate na,absent |
| `SPT_6_disableUntaint/mispredict_not_taken` | gem5-spt (inferred from name; no run_config in dir) | NO-ANN | 5000 | 0 | 678 | 4322 | 919 | S:919 | 0 | 1860 | A:1860, SL:1543, S:919 | 91.8%; br_v0,ld; gate na,absent |
| `SPT_6_full/mispredict_not_taken` | gem5-spt (inferred from name; no run_config in dir) | NO-ANN | 27000 | 0 | 6045 | 20955 | 5441 | S:5429, L:12 | 12 | 9190 | A:9190, SL:6323, S:5429, L:12, PASS(recomputed):1 | 63.5%; br_v0,ld; gate na,absent |
| `SPT_6_full_fence/mispredict_not_taken` | gem5-spt | NO-ANN | 24000 | 0 | 4431 | 19569 | 4860 | S:4848, L:12 | 12 | 8386 | A:8386, SL:6323, S:4848, L:12 | 71.6%; br_v0,ld; gate na,absent |
| `SPT_6_full_invispec/mispredict_not_taken` | gem5-spt | NO-ANN | 23000 | 0 | 4897 | 18103 | 4636 | S:4346, L:290 | 290 | 8083 | A:8083, SL:5384, S:4346, L:290 | 74.0%; br_v0,ld; gate na,absent |
| `STT_6/mispredict_not_taken` | recon (per AUDIT.md #20; dir has no run_config) | NO-ANN | 100000 | 41500 | 825 | 57675 | 15633 | S:14606, F:1025, multi:F/S:2 | 1025 | 19024 | SL:23018, A:19024, S:14606, F:1027 | 100.0%; br_v0,ld,br; gate na,absent |
| `STT_6/mispredict_taken` | recon (per AUDIT.md #20; dir has no run_config) | NO-ANN | 100000 | 41854 | 884 | 57262 | 16999 | S:12292, F:3960, multi:F/S:747 | 3960 | 18603 | SL:21660, A:18603, S:12292, F:4707 | 100.0%; br_v0,ld,br; gate na,absent |
| `STT_6_interleave/mispredict_not_taken` | recon (per AUDIT.md #20; dir has no run_config) | NO-ANN | 237833 | 102134 | 885 | 134814 | 33730 | S:31356, F:2350, multi:F/S:24 | 2350 | 41388 | SL:59696, A:41388, S:31356, F:2374 | 100.0%; ld,br_v0,br; gate na,absent |
| `STT_6_interleave/mispredict_taken` | recon (per AUDIT.md #20; dir has no run_config) | NO-ANN | 236885 | 105246 | 1197 | 130442 | 43556 | S:23633, F:18189, multi:F/S:1734 | 18189 | 39564 | SL:47322, A:39564, S:23633, F:19923 | 100.0%; ld,br_v0,br; gate na,absent |
| `STT_all_amulet/mispredict_not_taken` | amulet/amulet-gem5-STT_AE-v1.1 |  | 31103 | 1 | 9215 | 21887 | 5970 | S:5970 | 0 | 6622 | SL:9292, A:6606, S:5970, PASS(recomputed):19 | 90.4%; br_v0,ld,br; gate na,absent |
| `STT_all_recon/mispredict_not_taken` | recon (per AUDIT.md #20; dir has no run_config) | NO-ANN | 47646 | 10681 | 10346 | 26619 | 6880 | S:6540, F:207, L:86, multi:F/S:43, multi:F/L:4 | 297 | 12116 | A:12096, SL:7623, S:6540, F:254, L:86, ...(+1) | 93.6%; br_v0,ld,br; gate na,absent |
| `STT_all_sttbuild/mispredict_not_taken` | stt |  | 31102 | 1 | 9211 | 21890 | 5970 | S:5970 | 0 | 6626 | SL:9291, A:6618, S:5970, PASS(recomputed):11 | 80.0%; br_v0,ld,br; gate na,absent |
| `_verify_ld_taken/mispredict_taken` | ? (no config in dir) |  | 1270 | 0 | 1270 | 0 | 0 | - | 0 | - | - | 100.0%; ld; gate absent |

## Defense-specific load checkers

| campaign / mode / kind | gem5 binary | ann caveat | tests | errors | hits | non-hits | near-miss (exactly 1 fail) | near-miss by criterion | near-miss with signal present | legacy br opaque non-hits | joint pass/fail pattern at best grid point (top 5) | records consistent w/ recorded verdict; checker families; gate eval |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `STT_6_invisispec/mispredict_not_taken` | amulet/amulet-gem5-InvisiSpec_AE-v1.1 |  | 1500 | 20 | 0 | 1480 | 444 | S:444 | 0 | - | SL:1036, S:444 | 100.0%; ld_invisispec,ld; gate na |
| `STT_6_invisispec/mispredict_taken` | amulet/amulet-gem5-InvisiSpec_AE-v1.1 |  | 1500 | 23 | 0 | 1477 | 442 | S:442 | 0 | - | SL:1035, S:442 | 100.0%; ld_invisispec,ld; gate na |
| `STT_6_invisispec_compound/mispredict_not_taken` | amulet/amulet-gem5-InvisiSpec_AE-v1.1 |  | 1500 | 0 | 192 | 0 | 0 | - | 0 | - | - | 100.0%; ld_invisispec_compound; gate  |
| `STT_6_invisispec_compound/mispredict_taken` | amulet/amulet-gem5-InvisiSpec_AE-v1.1 |  | 1500 | 0 | 43 | 0 | 0 | - | 0 | - | - | 100.0%; ld_invisispec_compound; gate  |
| `STT_6_speclfb/mispredict_not_taken` | amulet/amulet-gem5-SpecLFB_AE-v1.1 |  | 1500 | 0 | 0 | 1500 | 397 | S:397 | 0 | - | SL:970, S:397, SLU:81, SU:52 | 100.0%; ld_speclfb; gate direct |
| `STT_6_speclfb/mispredict_taken` | amulet/amulet-gem5-SpecLFB_AE-v1.1 |  | 1500 | 0 | 0 | 1500 | 0 | - | 0 | - | SLU:1051, SU:449 | 100.0%; ld_speclfb; gate direct |

## Reproduce

The analysis script was a scratch, read-only script (not in the repo). It does this: for each non-symlink `results/**/window-results.json` outside the excluded dirs, it loads full records from that file, or else from the sweep raw dir. It applies the letter rules above to each record, aggregates per test exactly as `pipeline.py:_aggregate_sweep_results` does, and dumps the counters. The JSON keys are `near_miss_by`, `joint` (test-level, best grid point), `grid_joint` (every grid-point record), `families`, `gate_eval`, `inconsistent_records`, `legacy_br_opaque_nonhit`, `near_miss_signal_present`, `gem5_binary`, and `no_branch_annotations_caveat`.
