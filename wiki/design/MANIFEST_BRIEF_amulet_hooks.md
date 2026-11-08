# Brief for the eval-manifest owner: AMuLeT-build changes (hooks-v2 session, 2026-11-08)

**For:** the agent that owns [`wiki/state/EVAL_MANIFEST.md`](../state/EVAL_MANIFEST.md) and `specs/defense_units.json`. These are proposed edits to that manifest, as read on 2026-11-08 15:00. Apply them to both files together, per the manifest's own rule.

**Status:** Anna has approved the decisions cited as "(Anna 2026-11-08)". Everything else is marked as a proposal or as open.

**Background** (read only if a change is unclear):
- [`wiki/findings/mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md`](../findings/mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md), section "CURRENT": everything learned on the AMuLeT builds.
- [`wiki/findings/audits/2026-10-28/full_configs.md`](../findings/audits/2026-10-28/full_configs.md), last section: AMuLeT's exact flags and an inventory of every AMuLeT-build config.
- `URGENT_TODO.md`, the 2026-11-08 items.

## A. Decisions the manifest does not reflect yet

1. **Footprint rows run shrunk caches (Anna 2026-11-08).**
   - E12-E14 currently list AMuLeT's flags as *the* eval configuration. Anna decided instead that the footprint eval keeps SimSpect's amplified geometry, as AMuLeT itself does for InvisiSpec (§4.5.1 Table 6). That means a 1 kB/2-way L1D (CleanupSpec 2 kB/4-way), with CleanupSpec at `--L1_TBEs=8`.
   - **The default eval runs use the shrunk configs.** AMuLeT's exact flags are used for only two things: (a) the timing/throughput experiments, and (b) confirming a bug found in the shrunk runs at AMuLeT's sizes (Anna 2026-11-08).
   - Both config sets exist now: `runconfigs/footprint/` (eval) and `runconfigs/amulet_parity/` (comparison).
2. **CleanupSpec TBE value is decided (Anna 2026-11-08):** never 2, which deadlocks 62% of tests; 8 for the eval; 256 for parity.
3. **Two STT builds, with different roles (Anna 2026-11-08):** `/work/stt` (E3) gives SimSpect's STT results, and amulet-STT (E4) is for AMuLeT comparisons. The Recon-family STTs stay as their own rows.
4. **E4 is unblocked.** The amulet-STT `se.py` glue now honours `--threat_model`/`--needsTSO`/`--STT`/`--implicit_channel` (Anna approved). It is unchanged without those flags; the backup is `se.py.bak-20261108-pre-threatmodel` and the diff is `gem5-hooks/amulet-STT/se_py_threatmodel_glue_20261108.diff`.
   - Smoke-tested 2026-11-08 with `--ruby` on that build: rc 0; `config.ini` shows `threatModel=Futuristic`, `needsTSO=true`.
   - The build's protocol is MESI_Two_Level (`build/variables/X86`).
5. **P-5 smoke test done:** under BiModeBP the SpecLFB branch force still fires (`BR:predict_force` identical to the Tournament run, then `resolve_hold stall=5000 mispred=1`).
6. **Scope (Anna 2026-11-08).** Each footprint criterion checks only what that defense's paper claims to protect.
   - InvisiSpec UV2 (MSHR contention, §VII p10) and KV1 (I-cache, fn. 2 p3) are out of scope.
   - CleanupSpec unXpec (cleanup timing) is not checked for now.
   - The CleanupSpec directory stays unobserved, with the reason in `cleanupspec.json` `why_not_observed`.
7. **Checker and harness state** (deployed to `/tests/simspect_fixed_20261030/`, 2026-11-08, md5-verified):
   - `check_footprint` by_pc fix: it had wrongly disqualified 114/3000 InvisiSpec tests and 202 CleanupSpec records.
   - CleanupSpec ownership rule ("count as both").
   - `gem5_common._unglue`: native debug-print residue no longer drops trace lines.
   - Hooks v2 on all three footprint builds; every trace starts with `META:hooks … ver=2:build=<name>`.

## B. Exact edits to the eval table

**Replace row E4 with:**

| E4 | STT, AMuLeT's build (AMuLeT-comparison STT; SimSpect's STT results come from E3) | `/work/amulet/amulet-gem5-STT_AE-v1.1/build/X86/gem5.opt` (MESI_Two_Level) | AMuLeT's: `--ruby --needsTSO=1 --STT=1 --implicit_channel=1 --threat_model=Futuristic`, TBEs 256, 32kB/8 L1D, 2MB/8 L2, `--cpu-clock=2GHz --sys-clock=2GHz --access-backing-store` (executor.py:208-250, benchmark_all.sh:51-53) | STT_6 (sound but incomplete for Futuristic; the Futuristic model is parked) | check_ld / check_br | `runconfigs/amulet_parity/run_config_STT_6_amuletstt_amulet_parity.jsonc` | none. The glue was fixed 2026-11-08 and smoke-tested with `--ruby`; never run on a testset. Prior: `STT_all_amulet` (05-28, pre-fix, superseded) |

**Replace rows E12-E14 with:**

| E12a | InvisiSpec, Futuristic (AMuLeT's mode) | `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt` (hooks v2) | `--ruby --scheme=FuturisticSafeInvisibleSpec --needsTSO=1 --allowSpecBuffHit=1`, L1D 1kB/2, TBEs 2 (amplified, = AMuLeT Table 6 row 3 for TBEs), L1I 32kB/4, L2 2MB/16 | STT_6 | check_footprint (`invisispec.json`) | `runconfigs/footprint/run_config_STT_6_invisispec_futuristic_footprint.jsonc` | P-2 open (needsTSO/allowSpecBuffHit for the eval arm; parity uses 0/0). Needs a D-1 bucket (DTLB replacement-on-hit deviation, present in every hit) before results are readable. Prior: `results/STT_6_invisispec_v2hooks_futuristic__20261107` (3000 tests, UV1 in 3000 after the by_pc fix, 0 NEW) |
| E12b | InvisiSpec, Spectre (SimSpect extra; AMuLeT did not run it) | same | as E12a with `--scheme=SpectreSafeInvisibleSpec` | STT_6 | check_footprint | `runconfigs/footprint/run_config_STT_6_invisispec_spectre_footprint.jsonc` | P-2, P-3 open. Prior: `..._v2hooks_spectre__20261107` (UV1 2995/3000 after the fix, 0 NEW) |
| E13 | CleanupSpec | `/work/amulet/amulet-gem5-CleanupSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt` (hooks v2) | `--ruby --needsTSO=0 --scheme_invisispec=UnsafeBaseline --scheme_cleanupcache=Cleanup_FOR_L1L2`, L1D 2kB/4, `--L1_TBEs=8` (L2/DC TBEs 2), L1I 32kB/4, L2 2MB/16 | STT_6 (0 RMW instructions, so UV3 is unreachable; see the RMW row) | check_footprint (`cleanupspec.json`, with the ownership rule) | `runconfigs/footprint/run_config_STT_6_cleanupspec_footprint.jsonc` | Must re-run, since the ownership rule and the by_pc fix both postdate the prior run. Debug flags `O3PipeView` only. Prior: `results/STT_6_cleanupspec_v2hooks__20261107` (TBE 8 arm: 38 UV4, 2 hits now victim-only) |
| E14 | SpecLFB | `/work/amulet/amulet-gem5-SpecLFB_AE-v1.1/build/X86/gem5.opt` (hooks v2) | `--scheme=Speclfb --caches --l2cache`, L1D 1kB/2, L1I 32kB/8, L2 2MB/16, Tournament BP | STT_6 | check_footprint (`speclfb.json`) | `runconfigs/footprint/run_config_STT_6_speclfb_footprint.jsonc` | P-5 (BP for the eval arm) open. Findings to bucket: UV6 (first load), walk-order (DECIDE), and **jmp-shadow, a new real bug** (`wiki/findings/bug/speclfb_jmp_shadow/README.md`; counting it in the paper is Anna's DECIDE). Prior: `results/STT_6_speclfb_v2hooks__20261107` (1300/1500 and 1452/1500 hits) |

**Edit the paragraph "Harness additions are the same on every row …"** to read:

> Harness additions are the same on every row: the SimSpect hook flags, the debug flags, the branch force and the resolve stall. Everything else matches the defense authors' configuration, except the deliberate amplification on the footprint rows E12-E14 (shrunk L1D/TBEs, Anna 2026-11-08, explained in the paper's discussion); these shrunk configs are the default eval runs. AMuLeT's exact flags (the T rows) are used only for timing numbers and for confirming bugs.

**Edit the "Decisions that change this manifest" list.**
- Under "E4": replace the line with "E4 unblocked 2026-11-08 (glue fixed)".
- Under "AMuLeT parity", record as decided:
  - P-1, shrunk caches for the eval and parity for comparisons;
  - the CleanupSpec TBE value (8 / 256);
  - P-4, fix the glue;
  - the reference for comparisons is AMuLeT's flags.
- Still open: P-2, P-3, P-5 for the eval arm, and the clock (the eval arm runs gem5's 1 GHz default, parity 2 GHz).

## C. New rows: AMuLeT timing and bug confirmation (same priority as the eval)

Add a section **"AMuLeT-parity runs: timing and bug confirmation only"** after the eval table. These rows are not the eval: the default runs are E12-E14 on the shrunk configs.

**Rule for every T-row:** run only from `runconfigs/amulet_parity/`, and check `config.ini` against `full_configs.md` before trusting any number. This is the urgent STATUS todo of 2026-11-08: the shrunk eval configs must never produce a timing number.

| # | experiment | build | run config | measures | status |
|---|---|---|---|---|---|
| T1 | InvisiSpec-Futuristic at AMuLeT parity | E12's binary | `runconfigs/amulet_parity/run_config_STT_6_invisispec_futuristic_amulet_parity.jsonc` (32kB/8, TBEs 256, `--needsTSO=0`, 2GHz, `--access-backing-store`) | timing: tests/hour per core and wall time to the first detection of UV1; plus re-running each E12 NEW bug at parity | config smoke-tested 2026-11-08 (leak on `inst-101824`); not run |
| T2 | CleanupSpec at AMuLeT parity | E13's binary | `…/run_config_STT_6_cleanupspec_amulet_parity.jsonc` | same, for UV4; plus re-running E13 NEW bugs at parity | config smoke-tested; not run |
| T3 | SpecLFB at AMuLeT parity | E14's binary | `…/run_config_STT_6_speclfb_amulet_parity.jsonc` (BiModeBP) | same, for UV6 and jmp-shadow; plus re-running E14 NEW bugs at parity | config smoke-tested, branch force confirmed; not run |
| T4 | amulet-STT at AMuLeT parity | E4's binary | `…/run_config_STT_6_amuletstt_amulet_parity.jsonc` | same; note that AMuLeT's STT finding KV3 (spec store → D-TLB) is outside our STT leakage function, so no detection target exists | config written 2026-11-08, glue smoke-tested; not run |
| T5 | AMuLeT's own campaigns on the same machine (baseline) | the four AMuLeT builds | AMuLeT repo `/work/amulet-repo` @ c871bdf, `src/benchmark_all.sh` with its own YAMLs | AMuLeT's tests/hour and time to detection on cafe2, so T1-T4 are compared on the same hardware rather than with the paper's numbers | not set up; AMuLeT needs its own trace extraction in each build (its AE trees have it) |

Add these notes under the T table:
- **Confirm new bugs at parity.** Before any NEW footprint bug is claimed, re-run its test once at parity (T1-T3 config), so a reviewer cannot call it an artifact of the shrunk caches. jmp-shadow already reproduced on a pristine build.
- **The comparison is not identical even at parity.** AMuLeT starts each test with a filled or flushed L1D, uses a 1-page sandbox (128 pages for STT), and decides relationally across 140 inputs. We run a cold cache per test and decide from one trace. State this beside every T number.

## D. Rows conditional on open decisions (add as "pending", not as eval rows)

| # | experiment | depends on | what it adds |
|---|---|---|---|
| C1 | **DECIDED (Anna 2026-11-08): RMW as a disjoint corpus.** A separate testset whose ld transmitters are value-neutral RMWs (`orq $0,(mem)`), run on E13 (CleanupSpec) and on the STT rows. It never mixes into the main STT_6 corpus. Being built (hooks-v2 session); give it its own row and results dir | a `diag_uv3_rmw` bucket (every CleanupSpec test is expected to show UV3) | the only way the STT_6 family reaches CleanupSpec UV3; RMW load halves are already protected on every other build (checked 2026-11-08) |
| C2 | 2-core CleanupSpec: does a speculative GETX invalidating another core's copy leak? | Anna's go-ahead | tests an unverified hypothesis from the RMW study (CleanupSpec assumes RFOs are non-speculative, p8 §4) |
| C3 | SpecLFB jmp-shadow as a counted finding: variant matrix + counterfactual as a paper figure | Anna's DECIDE (count it; contact the authors) | the evidence already exists: `/work/amulet/jmpshadow_probe/` |

## E. Lower priority: AMuLeT on builds it never tested (put at the bottom)

Add a final short section **"Later: AMuLeT on the other defenses"**. This is Anna's urgent STATUS todo of 2026-11-08, but it is planned after the eval.

**The goal:** run AMuLeT itself, with its own parameters, on every SimSpect defense AMuLeT never tested:
- E1 Unsafe;
- E2 Recon-STT;
- E3 upstream STT;
- E6 ReCon;
- E8 NDA, E9 DoM, E10 Doppelganger;
- E11 SPT;
- the STL build.

**What each needs:**
- AMuLeT's µarch-trace extraction ported into that build (AMuLeT adds it to each defense's gem5 code; check whether our v2 hooks can stand in for it);
- the contract AMuLeT would use for that defense (ARCH-SEQ for STT-like, CT-SEQ for footprint-like, AMuLeT §3.1 p5);
- a parity config taken from that build's own authors where AMuLeT has none.

**Status:** not planned; write the plan before any run.

## F. Small corrections to existing text

- **E12 blocker text:** "P-1 (cold cache at 32kB may lose the eviction hits)" is now moot for the eval row, which is shrunk. Keep it as a caveat on T1 only.
- **E13 blocker text:** "TBE value (TBE 2 deadlocked 62%)" is decided (8 / 256).
- **E14 blocker text:** "P-5 (smoke-test that the branch force still fires with BiModeBP)": the smoke test is done (A.5). P-5 is now only about the eval arm's predictor.
- **Prior-run cells:** cite the 2026-11-07 v2-hooks runs as prior and reference-only (they ran on `testsets_latest`, not the two-stage regeneration). For CleanupSpec, note that the prior run predates the ownership rule and the by_pc fix.
- **Per-row provenance columns (proposal):** add "hooks" (the trace's `META:hooks ver=` and `build=`) and "checker rev" (the `check_footprint.py` / `cleanupspec.json` md5 or git sha). Both changed on 2026-11-08, and results are not comparable across those versions.
