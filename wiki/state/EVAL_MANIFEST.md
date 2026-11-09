# Eval manifest: what we run, on what, from which model

**The one place that says what the eval is.** Last refreshed 2026-11-08 17:00 (simspect-c8).

**Sources consolidated here** (each brief's facts were checked against the files before merging):
- the "Main models per defense" tables from `STAGE1_alloy/models/MANIFEST.md` (stl-spec);
- the eval subset of the 33-row build list in [`../findings/audits/2026-11-07/HOOK_AUDIT.md`](../findings/audits/2026-11-07/HOOK_AUDIT.md);
- the two-phase brief (twophase-spt, now deleted);
- the STL handoff in [`../design/STL_SPECULATION.md`](../design/STL_SPECULATION.md) (stl-spec);
- `wiki/design/MANIFEST_BRIEF_SPT_v2.md` (resolve-hooks);
- `wiki/design/MANIFEST_BRIEF_amulet_hooks.md` (hooks-v2).

**Where things live:**
- Machine-readable copy: `specs/defense_units.json` (each unit's `eval` object, `model_families`, `amulet_parity_runs`, `pending_rows`); the dashboard unit inspector shows the units.
- Build facts: `specs/gem5_builds.json`. Model metadata: `specs/alloy_models.json`. Catalog of every `.als`: `STAGE1_alloy/models/MANIFEST.md`.
- Edit this file and `defense_units.json` together.

**Status rule (Anna, 2026-11-08): everything is NOT RUN for this eval.** All testsets will be regenerated from the two-stage models and every campaign re-run. Earlier campaigns are listed only as reference.

## How the pieces connect

```
 Alloy model family            STAGE1_alloy/models/...                 which leaks exist (symbolic)
   Stage 1    core model       <model>_core*.als (RI-only; SPT too)    → minimal leak skeletons ("cores")
   Stage 1.5  production model <model>.als + pin one core (round 2)     → full instances grown around each core, cores in parallel
      ▼
 testset                       testsets*/<model>/xml/                   one XML per leak instance
      │  Stage 2: parsexml.py + compile_annotate.py (per branch mode, or stl_bypass for STL)
      ▼
 programs                      testsets*/<model>/<mode>/{asm,ann}/      .s + .ann.json per test
      │  Stage 3: one run config = gem5 binary + flags + hook state + checker
      ▼
 eval unit (one row below)     runconfigs/... or results/<x>/run_config.jsonc
      │  checker (check_ld / check_br / check_footprint / STL window checker)
      ▼
 results                       results/<results_name>__<timestamp>/<mode>/<kind>/
```

**How models, builds and run configs relate:**
- **One model family feeds many builds.** The STT_6 family is the stimulus for every row except ReCon (Recon_6), SPT (SPT_6_oneLP_v2) and OTB.
- **One row = one gem5 binary with one flag set,** so each row has its own run config and its own results directory. Rows that share the Kaxiras-group binary `gem5-recon-modded` (Unsafe, STT, ReCon, NDA, DoM, Doppelganger) differ only in flags, and they are still separate runs.
- **Copy the run config verbatim** when reproducing a hit. It carries the full hook state (branch force, unresolved stall, fnc stall); see CLAUDE.md.

**Harness additions, the same on every row:**
- the SimSpect hook flags and debug flags;
- the derived branch force, the resolve stall, and the execution-validity gate. These are on all 8 hooked builds; see [`../design/RESOLUTION_HOOKS.md`](../design/RESOLUTION_HOOKS.md) and [`../findings/bug/BRANCH_ANNOTATION_AND_FORCE.md`](../findings/bug/BRANCH_ANNOTATION_AND_FORCE.md).

**Where rows deviate from the authors' configuration:** everything else matches it, with one deliberate exception. The footprint rows E12-E14 use an amplified geometry: shrunk L1D, and InvisiSpec 2 TBEs / CleanupSpec 8 (Anna, 2026-11-08; the paper's discussion explains it). These shrunk configs are the default eval runs. AMuLeT's exact flags (the T rows below) are used only for timing numbers and for confirming bugs.

**Before the final batch:**
- `make sync`. The lc/fnc-from-Commit-trace fix (`gem5_common.fill_retire_from_commit`, 2026-11-07) is in this repo and the cafe2 fixed copy, but not yet in `/tests/simspect`.
- Every final run config needs its `sample_fraction` set. The templates `runconfigs/fixed_20261030/*_fixed_latest.jsonc` still say `0.02` from validation.
- Point every final run config's `testset_dir` / `results_name` at the regenerated testsets.

**Naming:** this manifest says **Stage 1.5** for the pinned flesh-out that the briefs call "Stage 2 / round 2". That is the name in the pipeline figure and `URGENT_TODO.md` (decided 2026-11-02), because "Stage 2" already means concretization.

## The eval set (approved by Anna, 2026-11-08)

Anna: "ok im down with those builds. make sure we're gonna run all the stts separately." So each STT implementation is its own row with its own results. Roles (Anna, 2026-11-08): E3 gives SimSpect's STT results; E4 is only for comparing with AMuLeT; E2 stays its own row. Every row is **NOT RUN**, and its testset will be the two-stage regeneration of the listed family.

| # | defense | gem5 binary | flags that make it this defense | model family | checker | run config | blocker / known causes / prior runs (reference only) |
|---|---|---|---|---|---|---|---|
| E1 | Unsafe (control: every test should leak) | `/work/gem5-recon-modded/build/X86/gem5.opt` | `--scheme=0` (no shadows, `decode.cc:685`) | STT_6 | check_ld / check_br | to create (copy E2's, scheme 0) | none; never run |
| E2 | STT, Kaxiras-group implementation ("Recon-STT") | same | `--scheme=2`; control + store shadows (`decode.cc:686-695`) | STT_6 | check_ld / check_br | `runconfigs/fixed_20261030/STT_6_reconmodded_fixed_latest.jsonc` (set `sample_fraction`) | **known real bug A2 dominates:** a load the defense marks tainted and speculative takes store-forwarded data and completes before the branch resolves. In round 4 (2% sample), 91/94 load tests hit, and all 185 test×mode runs were A2. Classifier: `STAGE3_gem5/triage/recon_stlf_check.py` + `triage/diag/diag_recon_stlf_bypass.py`. Prior: `results/STT_6_reconmodded_fixed_latest__20261108_012818` |
| E3 | STT, upstream (cwfletcher) implementation, Spectre: **SimSpect's STT results** | `/work/stt/build/X86/gem5.opt` | `se.py --scheme=2`; our glue sets Spectre and `needsTSO=0`, the authors' `run_stt.sh` uses `needsTSO=1` (HOOK_AUDIT decision) | STT_6 | check_ld / check_br | `runconfigs/fixed_20261030/STT_6_stt_fixed_latest.jsonc` (set `sample_fraction`) | needsTSO decision; prior: 0 hits in rounds 2 and 4 (`results/STT_6_stt_fixed_latest__20261108_012818`) |
| E4 | STT, AMuLeT's build: **AMuLeT comparison only** | `/work/amulet/amulet-gem5-STT_AE-v1.1/build/X86/gem5.opt` (MESI_Two_Level) | AMuLeT's: `--ruby --needsTSO=1 --STT=1 --implicit_channel=1 --threat_model=Futuristic`, TBEs 256, L1D 32kB/8, L2 2MB/8, `--cpu-clock=2GHz --sys-clock=2GHz --access-backing-store` (`executor.py:208-250`, `benchmark_all.sh:51-53`) | STT_6 (sound but incomplete for Futuristic; the Futuristic model is parked) | check_ld / check_br | `runconfigs/amulet_parity/run_config_STT_6_amuletstt_amulet_parity.jsonc` | **unblocked 2026-11-08** (Anna approved the glue fix): the `se.py` glue now honours `--threat_model`/`--needsTSO`/`--STT`/`--implicit_channel` (diff `gem5-hooks/amulet-STT/se_py_threatmodel_glue_20261108.diff`). Smoke test with `--ruby`: rc 0, `config.ini` `threatModel=Futuristic`, `needsTSO=true`. Never run on a testset. Prior: `STT_all_amulet` (05-28, pre-fix, superseded) |
| E5 | STT on SPT's STT-like sub-mode | `/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt` | unknown | STT_6 | check_ld / check_br | none | **unverified** that gem5-spt has an STT-only sub-mode; include only if it exists |
| E6 | ReCon | `gem5-recon-modded` | `--scheme=2 --allow_leaked` (`Options.py:422`) | Recon_6 | check_ld / check_br | to create (E2's + `--allow_leaked`) | open: `Recon_6.als` lacks `rf_from_most_recent_writer`, the same skeleton gap SPT v2 fixes (v2-1); no Recon v2 exists. Prior: `Recon_6__20260602_122016` (pre-fix) |
| E7 | ReCon OTB (getOldestTaint) | `gem5-recon-modded` | as E6 | OTB: decided 10-30 that OTB comes from Stage-2 interleave on the two-stage output; for now, DECIDE whether to use bugsynth `STT_6_otb2` + interleave | check_ld | none | OTB testset decision; OTB has never come out of enumeration |
| E8 | NDA (code enum `Delay`) | `gem5-recon-modded` | `--scheme=1` (`lsq_unit.cc:194-211`; email line 18) | STT_6 (no NDA model yet) | check_ld / check_br | to create (E2's, scheme 1) | none; never run |
| E9 | DoM | `gem5-recon-modded` | `--scheme=3` | STT_6 (no DoM model yet) | check_ld / check_br | to create (E2's, scheme 3) | none; never run |
| E10 | Doppelganger (on STT) | `gem5-recon-modded` | `--scheme=2 --address_prediction`, no `--ruby` (email line 19). The paper also evaluates NDA+D (`--scheme=1`) and DoM+D (`--scheme=3`) (Kvalsvik 2023 abstract p1) | STT_6 (no model yet) | check_ld / check_br | to create | a test only exercises the predictor if it trains it first (DECIDE) |
| E11 | SPT (SpectreSafeFence + DDIFT) | `/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt` | `--scheme=SpectreSafeFence --applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy --freeParam=3`; ours: `needsTSO=0`, classic caches; the authors' `run_spt.py:56` uses `--needsTSO=1 --ruby` (HOOK_AUDIT decision) | **SPT_6_oneLP_v2** (draft, awaiting sign-off) | check_ld / check_br; **store transmitters (`str`) have no checker** (check_ld's fallback scores the store's complete tick) | `runconfigs/fixed_20261030/SPT_6_oneLP_fence_fixed_latest.jsonc` (set `sample_fraction`; point at the v2 regen) | approve v2; needsTSO/Ruby decision; store-transmitter criterion. **Expect these v2 hits to classify, not count as bugs:** constant-derived transmitters (~10% of v2 instances; P3 not applied on purpose), and hits made public by unfed reads (P5). Tools: `STAGE3_gem5/triage/spt_cond_slice.py`, `spt_taint_probe.py`, `triage/diag/`. Prior: round 4 ran the OLD model; all 341 hit tests were model or concretization artifacts (`results/SPT_6_oneLP_fence_fixed_latest__20261108_012818`) |
| E12a | InvisiSpec, Futuristic (AMuLeT's mode) | `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt` (hooks v2) | shrunk eval config: `--ruby --scheme=FuturisticSafeInvisibleSpec --needsTSO=1 --allowSpecBuffHit=1`, L1D 1kB/2, TBEs 2 (AMuLeT's own amplification, Table 6 row 3), L1I 32kB/4, L2 2MB/16 | STT_6 | check_footprint (`invisispec.json`) | `runconfigs/footprint/run_config_STT_6_invisispec_futuristic_footprint.jsonc` | P-2 open for this row (needsTSO/allowSpecBuffHit; the parity run uses 0/0). Needs a D-1 bucket (a DTLB replacement-on-hit deviation present in every hit) before results are readable. Prior: `results/STT_6_invisispec_v2hooks_futuristic__20261107` (3000 tests, UV1 in 3000 after the by_pc fix, 0 NEW) |
| E12b | InvisiSpec, Spectre (a SimSpect extra; AMuLeT did not run it) | same | as E12a with `--scheme=SpectreSafeInvisibleSpec` | STT_6 | check_footprint | `runconfigs/footprint/run_config_STT_6_invisispec_spectre_footprint.jsonc` | P-2, P-3 open. Prior: `..._v2hooks_spectre__20261107` (UV1 2995/3000 after the fix, 0 NEW) |
| E13 | CleanupSpec | `/work/amulet/amulet-gem5-CleanupSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt` (hooks v2) | shrunk eval config: `--ruby --needsTSO=0 --scheme_invisispec=UnsafeBaseline --scheme_cleanupcache=Cleanup_FOR_L1L2`, L1D 2kB/4, `--L1_TBEs=8` (decided; never 2), L2/DC TBEs 2, L1I 32kB/4, L2 2MB/16 | STT_6 (0 RMW instructions, so UV3 is unreachable; see C1) | check_footprint (`cleanupspec.json`, with the ownership rule "count as both") | `runconfigs/footprint/run_config_STT_6_cleanupspec_footprint.jsonc` | must re-run: the ownership rule and the by_pc fix both postdate the prior run. Debug flags `O3PipeView` only (a native DPRINTF glues lines). Prior: `results/STT_6_cleanupspec_v2hooks__20261107` (TBE 8 arm: 38 UV4; 2 hits now victim-only) |
| E14 | SpecLFB | `/work/amulet/amulet-gem5-SpecLFB_AE-v1.1/build/X86/gem5.opt` (hooks v2) | shrunk eval config: `--scheme=Speclfb --caches --l2cache`, L1D 1kB/2, L1I 32kB/8, L2 2MB/16, Tournament predictor | STT_6 | check_footprint (`speclfb.json`) | `runconfigs/footprint/run_config_STT_6_speclfb_footprint.jsonc` | P-5 open for this row's predictor (BiModeBP keeps the branch force working; smoke-tested). Findings to bucket: UV6 (the first load), walk-order (DECIDE), and **jmp-shadow, a new real bug** (`wiki/findings/bug/speclfb_jmp_shadow/README.md`; whether the paper counts it is Anna's DECIDE). Prior: `results/STT_6_speclfb_v2hooks__20261107` (1300/1500 and 1452/1500 hits) |

Paths starting `testsets_latest/`, `runconfigs/fixed_20261030/` and `results/` are in the fixed-harness copy on cafe2, `/tests/simspect_fixed_20261030/` (the run configs are also in this repo, as are `runconfigs/footprint/` and `runconfigs/amulet_parity/`).

**Proposed provenance (not yet implemented):** record in each campaign the trace's `META:hooks ver=` / `build=`, plus the checker revision (`check_footprint.py` / `cleanupspec.json` md5 or git sha). Both changed on 2026-11-08, so results are not comparable across those versions.

**Not in the eval set** (optional or retired). Row numbers refer to HOOK_AUDIT's build list.
- SPT variants #21-#25 (Futuristic, InvisibleSpec, ImpFlow=Ignore, disableUntaint).
- The June latency experiments #15/#16/#26 (`se_slowcomm.py`, `se_exp.py`); the STT race leaks only appear there.
- DoM+ReCon #6; STT+Doppelganger+bypass #10; InvisiSpec on classic caches #28.
- STT-Futuristic on `/work/stt` #18 (unreachable, and parked by Anna 2026-11-07).
- stt-dbg #19; the unhooked recon control #11; SDO #33 (never built).

## AMuLeT-parity runs: timing and bug confirmation only

These rows are not the eval; the default runs are E12-E14 on the shrunk configs. They have the same priority as the eval (hooks-v2 brief).

**Rule for every T row:** run only from `runconfigs/amulet_parity/`, and check `config.ini` against `wiki/findings/audits/2026-10-28/full_configs.md` before trusting any number. The shrunk eval configs must never produce a timing number (STATUS urgent todo, 2026-11-08).

| # | experiment | build | run config | measures | status |
|---|---|---|---|---|---|
| T1 | InvisiSpec-Futuristic at AMuLeT parity | E12's binary | `runconfigs/amulet_parity/run_config_STT_6_invisispec_futuristic_amulet_parity.jsonc` (32kB/8, TBEs 256, `--needsTSO=0`, 2GHz, `--access-backing-store`) | tests per hour per core, and wall time to the first UV1 detection; plus re-running each E12 NEW bug at parity | config smoke-tested 2026-11-08 (leak on `inst-101824`); not run |
| T2 | CleanupSpec at AMuLeT parity | E13's binary | `…/run_config_STT_6_cleanupspec_amulet_parity.jsonc` (TBEs 256) | the same, for UV4; plus E13 NEW bugs at parity | config smoke-tested; not run |
| T3 | SpecLFB at AMuLeT parity | E14's binary | `…/run_config_STT_6_speclfb_amulet_parity.jsonc` (BiModeBP) | the same, for UV6 and jmp-shadow; plus E14 NEW bugs at parity | config smoke-tested, branch force confirmed; not run |
| T4 | amulet-STT at AMuLeT parity | E4's binary | `…/run_config_STT_6_amuletstt_amulet_parity.jsonc` | the same. AMuLeT's STT finding KV3 (a speculative store reaching the D-TLB) is outside our STT leakage function, so there is no detection target | config written, glue smoke-tested; not run |
| T5 | AMuLeT's own campaigns on the same machine (baseline) | the four AMuLeT builds | AMuLeT repo `/work/amulet-repo` @ c871bdf, `src/benchmark_all.sh` with its own YAMLs | AMuLeT's tests per hour and time to detection on cafe2, so T1-T4 are compared on the same hardware, not with the paper's numbers | not set up; AMuLeT needs its own trace extraction in each build (its AE trees have it) |

- **Confirm new bugs at parity.** Before claiming any NEW footprint bug, re-run its test once at parity (the T1-T3 configs), so a reviewer can't call it an artifact of the shrunk caches. jmp-shadow already reproduced on a pristine build.
- **Even at parity the comparison is not identical, so state this beside every T number.**
  - AMuLeT starts each test with a filled or flushed L1D, uses a 1-page sandbox (128 pages for STT), and decides relationally across 140 inputs.
  - We start each test with a cold cache and decide from one trace.

## Pending rows (conditional on decisions; not eval rows yet)

| # | experiment | depends on | what it adds |
|---|---|---|---|
| C1 | **RMW as a disjoint corpus (DECIDED, Anna 2026-11-08).** (i) Interim: a post-processed corpus `testsets_latest/STT_6_rmw`, whose ld transmitters are value-neutral RMWs (`orq $0,(mem)`). (ii) Planned: a model variant `proposed/STT_6_rmwjmp.als` (draft, needs sign-off) that adds RMW and direct-jump kinds, pinned so every instance contains one. Runs on E13 and the STT rows, in its own row and results directory, and never mixes into the main STT_6 corpus. Being built by the hooks-v2 session | a `diag_uv3_rmw` bucket (every CleanupSpec test is expected to show UV3) | the only way the STT_6 family reaches CleanupSpec UV3; RMW load halves are already protected on every other build (checked 2026-11-08) |
| C2 | 2-core CleanupSpec: does a speculative GETX invalidating another core's copy leak? | Anna's go-ahead | tests an unverified hypothesis from the RMW study (CleanupSpec assumes RFOs are non-speculative, p8 §4) |
| C3 | SpecLFB jmp-shadow as a counted finding: a variant matrix and counterfactual as a paper figure | Anna's DECIDE (count it; contact the authors) | the evidence already exists in `/work/amulet/jmpshadow_probe/` |

## Two-stage model families (Stage 1 core → Stage 1.5 flesh-out)

**What a core file is:** not a separate model. Each `_core` file is the production model's defense block, byte-identical, plus only the Stage-1 minimality and the scope relaxation (`but 6` instead of `exactly 6`, idx symmetry-breaking removed), made by `proposed_twophase/derive_core.py`. All core files are **unapproved drafts**, including the `STT_6_core.als` prototype in `models/` (committed 2026-10-20, never signed off). Anna signs off clause by clause before any production campaign or paper number.

**Minimality (decided 2026-11-08, Anna): RI-only for every family, SPT included.** SPT can use RI-only now because SPT_6_oneLP_v2 contains the seed fix. RO+RI makes the STL cores impossible. The STT_6/Recon_6 core drafts are still RO+RI and must be re-derived; the owner is Anna's Alloy agent, and since these are `.als` drafts, per-change sign-off applies.

| family | production model (Stage 1.5 base) | Stage-1 core | Stage-1 minimality | Stage-1 result | Stage 1.5 |
|---|---|---|---|---|---|
| STT_6 | `STT_6.als` (approved) | `STT_6_core.als` (prototype, draft) | draft: RO+RI → **re-derive RI-only** | 2 cores, exhausted (Mac `testsets/STT_6__twophase_draft/`) | not built |
| Recon_6 | `Recon_6.als` (approved) | `proposed_twophase/Recon_6_core.als` (draft) | draft: RO+RI → **re-derive RI-only** | 2 cores, exhausted; the same 2 as STT, because Recon's reveal clause has no effect at this size (R-1) | not built |
| **SPT_6_oneLP_v2** | **`SPT_6_oneLP_v2.als`** (draft, awaiting sign-off; sha256 acb1f2e2) | **`proposed_twophase/SPT_6_oneLP_v2_core_ri.als`** (draft) | RI-only | 546 at `but 3`; 5,000 (capped) at `but 4` | not built |
| (v2 fallback) | — | `proposed_twophase/SPT_6_oneLP_v2_core_conservative.als` | none | 546 at `but 3` | — |
| (v2, not recommended) | — | `proposed_twophase/SPT_6_oneLP_v2_core.als` | RO+RI | 6 at `but 3`; nothing in 15 min at `but 4` | — |
| (pre-v2, provenance only) | `SPT_6_oneLP.als` (sha256 713d0904, unchanged) | `proposed_twophase/SPT_6_oneLP_core_conservative.als` / `SPT_6_oneLP_core.als` | none / RO+RI | 20,000 capped / 0 (the unperturbed-seed dead end) | — |
| STT_6_stl | `STT_6_stl.als` (approved 2026-10-28) | `proposed_twophase/STT_6_stl_core.als` (draft) | RI-only (RO+RI is UNSAT by construction) | **306 cores, exhausted** at ≤6 instructions in 23 min | not built |
| Recon_6_stl | `proposed/Recon_6_stl.als` (draft) | `proposed_twophase/Recon_6_stl_core.als` (draft) | RI-only | was running since 13:58 (cap 20,000, 4 h); see `~/Library/Logs/simspect/twophase_Recon_6_stl.log` | not built |
| SPT STL | `proposed/SPT_6_oneLP_stl.als` (draft, derived from the pre-v2 model; generates 0) | `proposed_twophase/SPT_6_oneLP_stl_core_conservative.als` (draft) | none | UNSAT at ≤3 and ≤4: SPT's state-minimality (RS) conflicts with the alias fact; the seed fix does not help (stl-spec probe) | blocked (RS DECIDE; re-derive from v2) |
| STT_6_multisource (OTB) | `STT_6_multisource.als` | none | — | never enumerated | — |

**Stage 1.5:**
- **Not built for any family.** Anna's Alloy agent owns the two-stage ladder: `stage_seed.py` / `stage_pipeline.py` are an unwired STT prototype, and making them parallel is the open TODO.
- So every "two-stage" row is Stage-1-only so far, and **no two-stage testset exists for any defense.**

**Where the Alloy runs: the cafe2 `gem5_dev` container (decided 2026-11-08, Anna).**
- The container has Java 17 (`/usr/bin/java`, 17.0.15) and `alloy6.jar`, and `testsets_latest` was enumerated there in June.
- `run_stage1.py`'s Java and disk-guard paths are now configurable (`SIMSPECT_JAVA` / `SIMSPECT_DISK`); the Mac defaults are kept.
- Still needed: `a6CountModels.class` in `/tests/simspect/STAGE1_alloy/` (only the `.java` is there; the fixed copy has the `.class`).

**If SPT's Stage 1.5 volume is unwieldy** (its RI-only Stage 1 caps at 5,000 already at `but 4`), a scope ladder (enumerate N = 3..6 and keep the smallest distinct shapes) is the smaller but still conservative alternative.

## Testsets: what exists (all NOT RUN for this eval)

| testset | where | size | built from | use |
|---|---|---|---|---|
| two-stage regeneration of every family | — | — | the families above (SPT from v2) | **the eval's testsets; not built** (regenerate everything once the two-stage model exists, Anna 2026-11-08) |
| `testsets_latest/STT_6`, `Recon_6` | cafe2 `/tests/simspect_fixed_20261030/` | 150,000 programs per branch mode | today's exact `.als` (sha256 7a6ac4c0 / 01252c82), generated 2026-06-03 at git e298a9e | current **flat** testsets; interim stimulus only |
| `testsets_latest/SPT_6_oneLP` | same | 150,000 per mode | pre-v2 `SPT_6_oneLP.als` (713d0904) | **pre-v2, provenance only** (63% of its instances read a register past a newer writer) |
| `testsets_latest/STT_6_rmw` | same | being built | post-processed STT_6 (C1) | the disjoint RMW corpus |
| `testsets_v2sample_{cleanupspec,invisispec}` | same | 1,500 per mode | fixed-seed (20261107) samples of `testsets_latest/STT_6` | hooks-v2 samples |
| Stage-1 core corpora (`*__twophase_draft*`) | Mac `testsets/` | see the family table | draft core models | input to Stage 1.5, not tests yet. The `SPT_6_oneLP__twophase_draft*` corpora are pre-v2, provenance only |
| `testsets/STT_6`, `Recon_6`, `SPT_6_oneLP`, `STT_all`, `SPT_6_full`, ... | cafe2 `/tests/simspect/testsets/` | 5k-400k | older `.als` (hashes in claudelog 2026-11-07) | **stale, don't use** |
| `testsets/STT_6_stl` | cafe2 `/tests/simspect/testsets/` | 60 | `STT_6_stl.als` | hook test only |

Why `testsets_latest` counts as current even though `parsexml.py` changed since June: its provenance hash is 30de6b77 and today's is 2096e32a, but the diff (checked 2026-11-08) only adds three things. These testsets use none of them, and the instruction table is identical (28e77a1d):
- the STL `stl_bypass` mode;
- commit-split model support;
- a commit-boundary rule that skips interleave-inserted steps.

## Alloy models: which ones are up to date

"Current" means the file in `STAGE1_alloy/models/` is approved and the newest testset was built from exactly that file. Every approved production model is unchanged since git e298a9e (2026-06-03).

| model | role | approved? | newest testset from this exact file | pending proposals (none applied to approved files) |
|---|---|---|---|---|
| `STT_6.als` | production; stimulus for most rows | yes | flat `testsets_latest/STT_6` | P5 (a skeleton-wide unfed-read fact) would touch every model |
| `Recon_6.als` | production; ReCon | yes | flat `testsets_latest/Recon_6` | add `rf_from_most_recent_writer` (it lacks it; the same gap as SPT's v2-1) |
| **`SPT_6_oneLP_v2.als`** | **the SPT model for the final batch** | **draft**: sign-off pending, after the cafe2 "lost" check reports | none yet (3,000 scratch instances, `results/spt_v2_20261108/`) | flip `specs/alloy_models.json` tier `variant` → `production` on approval |
| `SPT_6_oneLP.als` | pre-v2 SPT, provenance only | yes (kept unchanged) | `testsets_latest/SPT_6_oneLP` | superseded by v2 |
| `STT_6_stl.als` | STL stimulus for the STT family | yes (2026-10-28) | 60-test hook testset | `rf` vs atom-based alias fact (DECIDE) |
| `STT_6_multisource.als` | OTB variant | yes (variant) | none (never enumerated) | OTB testset decision (E7) |
| `STT_6_commitsplit.als` | commit-boundary variant | yes (2026-10-29) | 20k per mode, fixed copy | review DECIDE in `URGENT_TODO.md` |
| `proposed/Recon_6_stl.als`, `proposed/SPT_6_oneLP_stl.als`, `proposed/STT_6_shadows.als`, `proposed/STT_6_rmwjmp.als` | STL / shadows / RMW drafts | drafts | scratch only | approvals pending (stl-spec, hooks-v2) |
| NDA, DoM, Doppelganger | (no model) | — | rows E8-E10 use STT_6 (sound, incomplete) | DECIDE: write a defense block per scheme |

**SPT_6_oneLP_v2: what changed** (resolve-hooks; checked by simspect-c8 against `SPT_6_oneLP.als`: exactly these four edits, each marked `[v2-n]`, everything else byte-identical).

| | change | why | effect |
|---|---|---|---|
| v2-1 | add `rf_from_most_recent_writer`, verbatim from `STT_6.als:161-170` | only STT_6 had it; in 68% of the old SPT testset an rf edge reads a register past a newer writer, so parsexml's program is not the instance | removes only instances no register machine can realize |
| v2-2 | protection seed computed over the perturbed program: `o_p[p] - ((Inreg + Inaddr) - i_p[p].outreg.(rf_p[p]))`, and `[p]` at the call site | the old seed ignored perturbations, so removal minimality could never shrink it and the SPT core was empty | identical to the old seed when nothing is perturbed (scratch `eq_base`: 0 counterexamples), and a subset under every perturbation. So it changes no leak verdict and loses no instance; it adds instances (≥500 capped in production) and makes SPT cores satisfiable. It is **not** the A1 seed rewrite in `ALLOY_MODEL_CHANGES.md` |
| v2-3 | base clause `not secure_speculation_scheme_p[no_p]` (≥1 insecure transmitter) instead of `one_insecure_…` (exactly 1) | the skeleton form STT/Recon use; SPT alone pruned two-leaker tests | strictly adds instances; `xm` still names the one the checker scores |
| v2-4 | declassification removes only the transmitted value and its producer (`.*(~rf_p)`), not the whole rf+ddi backward cone | SPT untaints backward only through MOV, and through invertible arithmetic when all but one input is public (paper §6 "Untaint rules"; gem5-spt `rob_impl.hh:853-878`) | the protection set becomes a superset of SPT's (more tests); some hits will be SPT legitimately untainting through mov/add, which the x86 slicer classifies |

**Not included, on purpose** (Anna prefers too many tests): P3, which drops constant-derived transmitters, and P5, the skeleton-wide unfed-read fact. Both are in `ALLOY_MODEL_CHANGES.md`.

**Evidence** (`results/spt_v2_20261108/`):
- v2 is satisfiable: 3,000 instances in 2 min at `exactly 6`.
- Shape census, old → v2: stale rf 63% → 0, clean 23% → 58%, unfed read 28% → 33%, constant-derived transmitter 2.4% → 9.6%.
- Differential: ≥500 instances in both, and ≥500 gained by v2.

**"Lost" checks** (old-useful and not new-useful):
- For v2 as a whole: only v2-4 can lose an instance, through minimality. An 8 h run is on cafe2 (`/tests/simspect_fixed_20261030/triage/spt_v2/lost_cafe2.log`); a 90-min Mac run found no counterexample.
- For v2-2 alone: simspect-c8's run is still going on the Mac (`results/twophase_stage1_2026-11-03/probe_spt_seed_20261107/differential_20261108/run.log`), with no counterexample yet.
- That run's log labels the model "sha 65eae944". That is the SHA-1 of the same unchanged file whose SHA-256 is 713d0904, not a different file.

## STL (store-to-load speculation): builds, per-defense scope, experiments

**What STL is here** (`STL_SPECULATION.md`):
- An older store's address is held unresolved, and the memory-dependence predictor is forced to say "no alias".
- A younger load to the same address reads the stale value. When the store's address resolves, gem5 squashes the load (memory-order violation).
- The window runs from load issue to that squash (Spectre v4).
- The opposite direction (predict alias when the addresses differ) opens no window and is only a negative control.

**Builds:**
- **Only `/work/gem5-recon-stl` has STL hooks.** It is stale: copied from recon-modded before the 2026-10-30 resolve hooks, so it has no `BR:` lines, the old-style branch force and no CPU-wake fix (HOOK_AUDIT: BORDERLINE).
  - Flags: `--stl-ann-file`, `--stl-store-stall-cycles N`, `--stl-alias-pred {no_alias,alias,off}`.
  - Schemes as on recon-modded.
  - Run config: `runconfigs/run_config_STT_6_stl.jsonc` (scheme 2, hold 5000, `no_alias`, fnc 150).
- **Every other build needs a port:** `gem5-hooks/stl/apply_stl_hooks.py <gem5_root>` plus a rebuild.

**Checker: there is no STL window checker yet.** check_ld / check_br verdicts mean nothing on STL tests (there is no `lc`, and `fnc` is the store). Until it exists, `gem5-hooks/stl/stl_hooktest.py` scores them.

**STL this round (decided 2026-11-08, Anna): the Kaxiras-group builds only.**
- Rebuild `/work/gem5-recon-stl` from today's `gem5-recon-modded`, which adds the resolve hooks.
- Write the STL window checker.
- That covers E1, E2, E6, E8, E9 and E10.
- No port to the AMuLeT builds or gem5-spt this round. **Not started; no owner yet.**

| eval row | STL in its threat model? | STL model family | can it run today? |
|---|---|---|---|
| E1 Unsafe | control | STT_6_stl | yes, on `gem5-recon-stl --scheme=0` (the control in the hook test) |
| E2 STT Kaxiras | yes (`decode.cc:686-695`) | STT_6_stl | yes, on `gem5-recon-stl` (stale); no window checker |
| E3 STT upstream | no: no store shadows (`rob_impl.hh:444-495`); a bypass leak is expected by design | STT_6_stl only as a labelled control | no hooks (not this round) |
| E4 STT AMuLeT (Futuristic) | yes (a store-load alias is a squash source under Futuristic) | STT_6_stl | no hooks (not this round) |
| E6 ReCon | yes (runs on Recon-STT's shadow tracker) | Recon_6_stl (draft) | partly: ReCon mode on `gem5-recon-stl` is not verified |
| E8 NDA, E9 DoM, E10 Doppelganger | probably (same shadow tracker; not verified in code) | STT_6_stl | on `gem5-recon-stl --scheme=1/3` (+ `--address_prediction`), untested |
| E11 SPT (Spectre configs) | no (branch-only visibility point) | — | no hooks |
| E12 InvisiSpec | Futuristic mode only (InvisiSpec Sec. IV Table I) | STT_6_stl | no hooks (not this round) |
| E13 CleanupSpec, E14 SpecLFB | yes (CleanupSpec Sec. 2.1; SpecLFB Sec. 5) | STT_6_stl | no hooks (not this round) |
| E7 OTB | n/a (two-source merge shape) | — | — |

**STL experiments done:**
- Hook test, 60 `STT_6_stl` tests on `gem5-recon-stl` (2026-10-30): 58/60 valid bypasses. STT sent 0/28 load transmitters in the window vs Unsafe 28/28; the `alias` and hold-0 controls gave 0 (`results/STT_6_stl_hooktest/controls/`).
- Shadows store-only + alias (2026-11-07): STT 0/32 vs Unsafe 32/32 (`results/STT_6_shadows_draft/`).

## Decisions

**Decided (Anna, 2026-11-08):**
- Scheme 1 = NDA.
- Regenerate every testset once the two-stage model exists; everything is NOT RUN.
- Stage-1 minimality: RI-only for every family.
- STL this round: the Kaxiras-group builds (rebuild `gem5-recon-stl`, write the STL checker).
- SPT seed fix (now inside v2).
- Alloy runs on the cafe2 container.
- Footprint rows run shrunk caches; AMuLeT parity is only for timing and bug confirmation (P-1).
- CleanupSpec TBEs: 8 for the eval, 256 for parity, never 2.
- amulet-STT glue fixed, so E4 is unblocked (P-4).
- STT roles: E3 = SimSpect's STT results; E4 = AMuLeT comparison.
- RMW as a disjoint corpus (C1).
- Comparisons use AMuLeT's flags as the reference.

**Open:**
- **Models:**
  - approve `SPT_6_oneLP_v2.als` (after the cafe2 "lost" check);
  - P3 (proposed: no);
  - P5, the unfed-read fact for all models;
  - give `Recon_6.als` the rf fact;
  - approve each core draft clause by clause, and re-derive the STT_6/Recon_6 cores RI-only;
  - NDA / DoM / Doppelganger defense blocks.
- **Pipeline:**
  - build and parallelize Stage 1.5, then regenerate;
  - set `sample_fraction` for the final batch;
  - `make sync` before the final batch.
- **Checkers:**
  - a criterion for store transmitters (E11 `str`);
  - the InvisiSpec D-1 bucket;
  - the SpecLFB walk-order rule;
  - whether jmp-shadow counts in the paper, and contacting the authors (C3).
- **Configs:**
  - P-2 (InvisiSpec needsTSO/allowSpecBuffHit for the eval rows);
  - P-3 (keep E12b, Spectre);
  - P-5 (SpecLFB predictor for the eval row);
  - the eval rows' clock (they run gem5's 1 GHz default; parity runs 2 GHz);
  - needsTSO / Ruby for E3 and E11.
- **STL:**
  - who rebuilds `gem5-recon-stl` and writes the checker, and the checker's design;
  - approve `Recon_6_stl`;
  - SPT STL's RS rule (exempt the alias location / drop RS / skip);
  - `rf` vs atom alias fact;
  - `STT_6_shadows`;
  - whether the forced memory-dependence prediction counts as "the predictor".
- **Other:**
  - how OTB tests are produced (E7);
  - whether gem5-spt has an STT sub-mode (E5);
  - the Doppelganger training stimulus (E10);
  - C2.

## Later: AMuLeT on the defenses it never tested

This is Anna's urgent STATUS todo of 2026-11-08, planned for after the eval.

**The goal:** run AMuLeT itself, with its own parameters, on every SimSpect defense AMuLeT never tested: E1, E2, E3, E6, E8, E9, E10, E11, and the STL build.

**What each needs:**
- AMuLeT's µarch-trace extraction ported into that build (check whether our v2 hooks can stand in for it);
- the contract AMuLeT would use for that defense (ARCH-SEQ for STT-like defenses, CT-SEQ for footprint-like ones; AMuLeT §3.1 p5);
- a parity config taken from that build's own authors, where AMuLeT has none.

**Status:** not planned; write the plan before any run.
