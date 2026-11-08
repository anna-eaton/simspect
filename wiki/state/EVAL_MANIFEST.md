# Eval manifest: what we run, on what, from which model

**The one place that says what the eval is.** Last refreshed 2026-11-08 (simspect-c8).

**Sources consolidated here:**
- the "Main models per defense" tables from `STAGE1_alloy/models/MANIFEST.md` (stl-spec);
- the eval subset of the 33-row build list in [`../findings/audits/2026-11-07/HOOK_AUDIT.md`](../findings/audits/2026-11-07/HOOK_AUDIT.md);
- the two-phase / SPT brief `wiki/design/MANIFEST_BRIEF_twophase_and_SPT.md` (twophase-spt);
- the STL handoff at the top of [`../design/STL_SPECULATION.md`](../design/STL_SPECULATION.md) (stl-spec).

**Where things live:**
- Machine-readable copy: `specs/defense_units.json` (each unit's `eval` object, plus `model_families`); the dashboard unit inspector shows it.
- Build facts: `specs/gem5_builds.json`. Model metadata: `specs/alloy_models.json`. Catalog of every `.als`: `STAGE1_alloy/models/MANIFEST.md`.
- Edit this file and `defense_units.json` together.

**Status rule (Anna, 2026-11-08): everything is NOT RUN for this eval.** All testsets will be regenerated from the two-stage models and every campaign re-run. Earlier campaigns are listed only as reference.

## How the pieces connect

```
 Alloy model family            STAGE1_alloy/models/...                 which leaks exist (symbolic)
   Stage 1    core model       <model>_core.als (per-family minimality) → minimal leak skeletons ("cores")
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

- **One model family feeds many builds.** The STT_6 family is the stimulus for every row except ReCon (Recon_6), SPT (SPT_6_oneLP) and OTB.
- **One row = one gem5 binary with one flag set,** so each row has its own run config and its own results directory. Rows that share the Kaxiras-group binary `gem5-recon-modded` (Unsafe, STT, ReCon, NDA, DoM, Doppelganger) differ only in flags, and they are still separate runs.
- **Copy the run config verbatim** when reproducing a hit. It carries the full hook state (branch force, unresolved stall, fnc stall); see CLAUDE.md.
- **Harness additions are the same on every row:** the SimSpect hook flags and debug flags. Everything else should match the defense authors' configuration (Anna, 2026-11-08). Where it doesn't yet, the row says so.
- **Naming:** the brief calls the pinned flesh-out "Stage 2 / round 2". This manifest uses **Stage 1.5**, the name in the pipeline figure and `URGENT_TODO.md` (decided 2026-11-02), because "Stage 2" already means concretization.

## The eval set (approved by Anna, 2026-11-08)

Anna: "ok im down with those builds. make sure we're gonna run all the stts separately." So each STT implementation is its own row with its own results. Every row's eval status is **NOT RUN**. Its testset will be the two-stage regeneration of the listed family; until then the current flat testset is `testsets_latest/<model>`.

| # | defense | gem5 binary | flags that make it this defense | model family | checker | run config | blocker / prior runs (reference only) |
|---|---|---|---|---|---|---|---|
| E1 | Unsafe (control: every test should leak) | `/work/gem5-recon-modded/build/X86/gem5.opt` | `--scheme=0` (no shadows, `decode.cc:685`) | STT_6 | check_ld / check_br | to create (copy E2's, scheme 0) | none; never run |
| E2 | STT, Kaxiras-group implementation ("Recon-STT") | same | `--scheme=2`; control + store shadows (`decode.cc:686-695`) | STT_6 | check_ld / check_br | `runconfigs/fixed_20261030/STT_6_reconmodded_fixed_latest.jsonc` | prior: round 4 on flat `testsets_latest/STT_6` (`results/STT_6_reconmodded_fixed_latest__20261108_012818`) |
| E3 | STT, upstream (cwfletcher) implementation, Spectre | `/work/stt/build/X86/gem5.opt` | `se.py --scheme=2`; our glue sets Spectre and `needsTSO=0`, the authors' `run_stt.sh` uses `needsTSO=1` (HOOK_AUDIT decision) | STT_6 | check_ld / check_br | `runconfigs/fixed_20261030/STT_6_stt_fixed_latest.jsonc` | needsTSO decision; prior: round 4 (`results/STT_6_stt_fixed_latest__20261108_012818`) |
| E4 | STT, AMuLeT's build | `/work/amulet/amulet-gem5-STT_AE-v1.1/build/X86/gem5.opt` | AMuLeT's: `--ruby --needsTSO=1 --STT=1 --implicit_channel=1 --threat_model=Futuristic` + TBEs 256, 32kB/8 L1D, 2MB/8 L2, `--sys-clock=2GHz`, `--access-backing-store` (HOOK_AUDIT parity section) | STT_6 (sound but incomplete for Futuristic; the Futuristic model is parked) | check_ld / check_br | none | **BLOCKED:** our `se.py:348-349` glue skips `config_scheme` whenever `--scheme` is set (always), so the threat model and needsTSO flags are ignored. Needs a 2-line config-glue edit, Anna's OK (P-4). `--ruby` never run on this build. Prior: `STT_all_amulet` (05-28, pre-fix, 100% errors) |
| E5 | STT on SPT's STT-like sub-mode | `/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt` | unknown | STT_6 | check_ld / check_br | none | **unverified** that gem5-spt has an STT-only sub-mode; include only if it exists |
| E6 | ReCon | `gem5-recon-modded` | `--scheme=2 --allow_leaked` (`Options.py:422`) | Recon_6 | check_ld / check_br | to create (E2's + `--allow_leaked`) | prior: `Recon_6__20260602_122016` (pre-fix) |
| E7 | ReCon OTB (getOldestTaint) | `gem5-recon-modded` | as E6 | OTB: decided 10-30 that OTB comes from Stage-2 interleave on the two-stage output; for now DECIDE bugsynth `STT_6_otb2` + interleave | check_ld | none | OTB testset decision; OTB has never come out of enumeration |
| E8 | NDA (code enum `Delay`) | `gem5-recon-modded` | `--scheme=1` (`lsq_unit.cc:194-211`; email line 18) | STT_6 (no NDA model yet) | check_ld / check_br | to create (E2's, scheme 1) | none; never run |
| E9 | DoM | `gem5-recon-modded` | `--scheme=3` | STT_6 (no DoM model yet) | check_ld / check_br | to create (E2's, scheme 3) | none; never run |
| E10 | Doppelganger (on STT) | `gem5-recon-modded` | `--scheme=2 --address_prediction`, no `--ruby` (email line 19). The paper also evaluates NDA+D (`--scheme=1`) and DoM+D (`--scheme=3`) (Kvalsvik 2023 abstract p1) | STT_6 (no model yet) | check_ld / check_br | to create | a test only exercises the predictor if it trains it first (DECIDE) |
| E11 | SPT (SpectreSafeFence + DDIFT) | `/work/gem5-spt/build/X86_MESI_Two_Level/gem5.opt` | `--scheme=SpectreSafeFence --applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy --freeParam=3`; ours: `needsTSO=0`, classic caches; the authors' `run_spt.py:56` uses `--needsTSO=1 --ruby` (HOOK_AUDIT decision) | SPT_6_oneLP | check_ld / check_br | `runconfigs/fixed_20261030/SPT_6_oneLP_fence_fixed_latest.jsonc` | needsTSO/Ruby decision; SPT model changes pending; prior: round 4 (`results/SPT_6_oneLP_fence_fixed_latest__20261108_012818`) |
| E12 | InvisiSpec | `/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt` | AMuLeT's: `--ruby --scheme=FuturisticSafeInvisibleSpec --needsTSO=0 --allowSpecBuffHit=0`, TBEs 256, L1D 32kB/8, L1I 32kB/8, L2 2MB/8, `--sys-clock=2GHz --access-backing-store`. Spectre mode as a labelled extra (P-3) | STT_6 | check_footprint (`specs/leakage/invisispec.json`) | parity config to create | P-1 (cold cache at 32kB may lose the eviction hits), P-2, P-3; prior: hooks-v2 sample runs on non-AMuLeT flags (`results/STT_6_invisispec_v2hooks_{spectre,futuristic}__20261107`) |
| E13 | CleanupSpec | `/work/amulet/amulet-gem5-CleanupSpec_AE-v1.1/build/X86_MESI_Two_Level/gem5.opt` | AMuLeT's: `--ruby --needsTSO=0 --scheme_invisispec=UnsafeBaseline --scheme_cleanupcache=Cleanup_FOR_L1L2`, TBEs 256, L1D 32kB/8, L1I 32kB/2, L2 2MB/8, `--sys-clock=2GHz --access-backing-store` | STT_6 | check_footprint (`cleanupspec.json`) | parity config to create | P-1; TBE value (TBE 2 deadlocked 62%); prior: `results/STT_6_cleanupspec_v2hooks__20261107` (TBE 2/8, L1D 2kB/4) |
| E14 | SpecLFB | `/work/amulet/amulet-gem5-SpecLFB_AE-v1.1/build/X86/gem5.opt` | AMuLeT's: `--scheme=Speclfb --bp-type=BiModeBP --caches --l2cache`, L1D 32kB/8, L1I 32kB/2, L2 2MB/8, `--sys-clock=2GHz` | STT_6 | check_footprint (`speclfb.json`) | parity config to create | P-1, P-5 (smoke-test that the branch force still fires with BiModeBP); prior: `results/STT_6_speclfb_v2hooks__20261107` (TournamentBP, L1D 1kB/2) |

Paths starting `testsets_latest/`, `runconfigs/fixed_20261030/` and `results/` are in the fixed-harness copy on cafe2, `/tests/simspect_fixed_20261030/` (the run configs are also in this repo).

**Not in the eval set** (optional or retired). Row numbers refer to HOOK_AUDIT's build list.
- SPT variants #21-#25 (Futuristic, InvisibleSpec, ImpFlow=Ignore, disableUntaint).
- The June latency experiments #15/#16/#26 (`se_slowcomm.py`, `se_exp.py`); the STT race leaks only appear there.
- DoM+ReCon #6; STT+Doppelganger+bypass #10; InvisiSpec on classic caches #28.
- STT-Futuristic on `/work/stt` #18 (unreachable, and parked by Anna 2026-11-07).
- stt-dbg #19; the unhooked recon control #11; SDO #33 (never built).

## Two-stage model families (Stage 1 core → Stage 1.5 flesh-out)

**What a core file is:** not a separate model. Each `_core` file is the production model's defense block, byte-identical, plus only the Stage-1 minimality and the scope relaxation (`but 6` instead of `exactly 6`, idx symmetry-breaking removed), made by `proposed_twophase/derive_core.py`. All core files are **unapproved drafts**, including the `STT_6_core.als` prototype in `models/` (committed 2026-10-20, never signed off). Anna signs off clause by clause before any production campaign or paper number.

**Minimality is set per family, not globally.** RO+RI makes the STL cores impossible, and with today's seed every removal rule makes the SPT cores empty. **Decided 2026-11-08 (Anna): RI-only for every family except SPT.** The STT_6/Recon_6 core drafts are still RO+RI and must be re-derived. Owner: Anna's Alloy agent; these are `.als` drafts, so per-change sign-off applies. SPT moves to RI-only too if the seed fix is signed off.

| family | production model (Stage 1.5 base) | Stage-1 core | Stage-1 minimality | Stage-1 result (Mac, gitignored `testsets/`) | Stage 1.5 |
|---|---|---|---|---|---|
| STT_6 | `STT_6.als` (approved) | `STT_6_core.als` (prototype, draft) | draft: RO+RI → **to re-derive RI-only** (decided) | 2 cores, exhausted (`STT_6__twophase_draft/`) | not built |
| Recon_6 | `Recon_6.als` (approved) | `proposed_twophase/Recon_6_core.als` (draft) | draft: RO+RI → **to re-derive RI-only** (decided) | 2 cores, exhausted; the same 2 as STT, because Recon's reveal clause has no effect at this size (R-1) (`Recon_6__twophase_draft/`) | not built |
| SPT_6_oneLP | `SPT_6_oneLP.als` (approved) | **`proposed_twophase/SPT_6_oneLP_core_conservative.als` = the default SPT core** (Anna approved making it the default on condition that it is more conservative, and it is: its instance set contains RO+RI's, which is empty) | none (base `one_insecure` + RR/RC/RS; over-generates). RI-only once the seed fix is signed off | **20,000, CAPPED** (`SPT_6_oneLP__twophase_draft_conservative/`) | not built |
| (superseded) | — | `proposed_twophase/SPT_6_oneLP_core.als` | RO+RI | 0, a dead end caused by the unperturbed protection seed (`SPT_6_oneLP__twophase_draft/`, kept for provenance) | — |
| STT_6_stl | `STT_6_stl.als` (approved 2026-10-28) | `proposed_twophase/STT_6_stl_core.als` (draft) | RI-only (RO+RI is UNSAT by construction) | **306 cores, exhausted** at ≤6 instructions in 23 min (`STT_6_stl__twophase_draft/`) | not built |
| Recon_6_stl | `proposed/Recon_6_stl.als` (draft) | `proposed_twophase/Recon_6_stl_core.als` (draft) | RI-only | running since 13:58 (858 at the last check; cap 20,000, 4 h) (`Recon_6_stl__twophase_draft/`) | not built |
| SPT_6_oneLP_stl | `proposed/SPT_6_oneLP_stl.als` (draft; generates 0) | `proposed_twophase/SPT_6_oneLP_stl_core_conservative.als` (draft) | none | UNSAT at ≤3 and ≤4: SPT's state-minimality (RS) conflicts with the alias fact | blocked (RS DECIDE) |
| STT_6_multisource (OTB) | `STT_6_multisource.als` | none | — | never enumerated | — |

- **Stage 1.5 is not built for any family.** Anna's Alloy agent owns the two-stage ladder: `stage_seed.py` / `stage_pipeline.py` are an unwired STT prototype, and making them parallel is the open TODO. So every "two-stage" row is Stage-1-only so far, and **no two-stage testset exists for any defense.**
- **Where the Alloy runs: the cafe2 `gem5_dev` container (decided 2026-11-08, Anna).** Until today `run_stage1.py` hardcoded Homebrew Java and a macOS disk-guard path. Both are now configurable (`SIMSPECT_JAVA` / `SIMSPECT_DISK`), and the Mac defaults are kept when they exist. Still needed on cafe2: `a6CountModels.class` in `/tests/simspect/STAGE1_alloy/` (only the `.java` is there; the fixed copy has the `.class`).
  - Correction to the brief: the cafe2 `gem5_dev` container **does** have Java 17 (`/usr/bin/java`, openjdk 17.0.15) and `alloy6.jar` (`/tests/simspect/STAGE1_alloy/`, `/tests/simspect_fixed_20261030/STAGE1_alloy/`), and `testsets_latest` was enumerated there in June (its `provenance.tar.gz` manifest).
  - So the container's 64 cores can run Stage 1 / 1.5 (checked 2026-11-08).
- **If SPT's Stage 1.5 volume is unwieldy** (its Stage 1 already exceeds 20,000), a scope ladder (enumerate N = 3..6 and keep the smallest distinct shapes) is the smaller but still conservative alternative.

## Testsets: what exists (all NOT RUN for this eval)

| testset | where | size | built from | use |
|---|---|---|---|---|
| two-stage regeneration of every family | — | — | the families above | **the eval's testsets; not built** (regenerate everything once the two-stage model exists, Anna 2026-11-08) |
| `testsets_latest/STT_6`, `SPT_6_oneLP`, `Recon_6` | cafe2 `/tests/simspect_fixed_20261030/` | 150,000 programs per branch mode | today's exact `.als` (sha256 7a6ac4c0 / 713d0904 / 01252c82), generated 2026-06-03 at git e298a9e | current **flat** testsets; interim stimulus only |
| `testsets_v2sample_{cleanupspec,invisispec}` | same | 1,500 per mode | fixed-seed (20261107) samples of `testsets_latest/STT_6` | hooks-v2 samples |
| Stage-1 core corpora (`*__twophase_draft*`) | Mac `testsets/` | see the family table | draft core models | input to Stage 1.5, not tests yet |
| `testsets/STT_6`, `Recon_6`, `SPT_6_oneLP`, `STT_all`, `SPT_6_full`, ... | cafe2 `/tests/simspect/testsets/` | 5k-400k | older `.als` (hashes in claudelog 2026-11-07) | **stale, don't use** |
| `testsets/STT_6_stl` | cafe2 `/tests/simspect/testsets/` | 60 | `STT_6_stl.als` | hook test only |

Why `testsets_latest` counts as current even though `parsexml.py` changed since June: its provenance hash is 30de6b77 and today's is 2096e32a, but the diff (checked 2026-11-08) only adds three things. These testsets use none of them, and the instruction table is identical (28e77a1d):
- the STL `stl_bypass` mode;
- commit-split model support;
- a commit-boundary rule that skips interleave-inserted steps.

## Alloy models: which ones are up to date

"Current" means the file in `STAGE1_alloy/models/` is approved and the newest testset was built from exactly that file. Every production model is unchanged since git e298a9e (2026-06-03).

| model | role | approved? | newest testset from this exact file | pending proposals (none applied) |
|---|---|---|---|---|
| `STT_6.als` | production; stimulus for most rows | yes | flat `testsets_latest/STT_6` | none |
| `Recon_6.als` | production; ReCon | yes | flat `testsets_latest/Recon_6` | add `rf_from_most_recent_writer` (P1 in [`ALLOY_MODEL_CHANGES.md`](ALLOY_MODEL_CHANGES.md)); it lacks it (grep) |
| `SPT_6_oneLP.als` | production; SPT | yes | flat `testsets_latest/SPT_6_oneLP` | P1-P5 in `ALLOY_MODEL_CHANGES.md` (resolve-hooks); the perturbation-aware protection seed (below) |
| `STT_6_stl.als` | STL stimulus for the STT family | yes (2026-10-28) | 60-test hook testset | `rf` vs atom-based alias fact (DECIDE) |
| `STT_6_multisource.als` | OTB variant | yes (variant) | none (never enumerated) | OTB testset decision (E7) |
| `STT_6_commitsplit.als` | commit-boundary variant | yes (2026-10-29) | 20k per mode, fixed copy | review DECIDE in `URGENT_TODO.md` |
| `proposed/Recon_6_stl.als`, `proposed/SPT_6_oneLP_stl.als`, `proposed/STT_6_shadows.als` | STL / shadows drafts | drafts | scratch only | approvals pending (stl-spec) |
| NDA, DoM, Doppelganger | (no model) | — | rows E8-E10 use STT_6 (sound, incomplete) | DECIDE: write a defense block per scheme |

**The SPT protection seed:**
- **The problem:** `SPT_6_oneLP.als:341` computes the starting protection set from the whole, unperturbed program. Removing an instruction or operand therefore never shrinks it, which is why every removal rule empties the SPT core.
- **The proposed fix:** compute it over the perturbed program (`o_p[p] - ((Inreg + Inaddr) - i_p[p].outreg.(rf_p[p]))`, plus `[p]` at `:232`). In the scratch probe, the RO+RI SPT core then has 6 cores at `but 3`.
- **It does not change what SPT protects.** This is not the A1 rewrite in `ALLOY_MODEL_CHANGES.md`, which changes the seed's contents.
  - The brief calls the fix "the A1 rework" and says it would change SPT semantics, but the differential check (`results/twophase_stage1_2026-11-03/probe_spt_seed_20261107/differential_20261108/`) shows the unperturbed seed is identical (0 counterexamples).
  - So which programs count as leaks is unchanged; only the minimality checks change.
  - Production SPT gains at least 500 instances (capped) that the old seed wrongly rejected. The "loses nothing" check is still running.
- **Status (decided 2026-11-08, Anna):** apply it once the "drops nothing" check returns 0 and Anna signs off the 2-line diff per file. SPT uses the conservative core until then, and keeps it as a fallback.
- **It does not fix SPT STL**, which fails for a different reason (RS vs the alias fact, stl-spec probe).

## STL (store-to-load speculation): builds, per-defense scope, experiments

**What STL is here** (`STL_SPECULATION.md`): an older store's address is held unresolved, the memory-dependence predictor is forced to say "no alias", and a younger load to the same address reads the stale value. When the store's address resolves, gem5 squashes the load (memory-order violation). The window runs from load issue to that squash (Spectre v4). The opposite direction (predict alias when the addresses differ) opens no window and is only a negative control.

**Builds:**
- **Only `/work/gem5-recon-stl` has STL hooks.** It is stale: copied from recon-modded before the 2026-10-30 resolve hooks, so it has no `BR:` lines, the old-style branch force and no CPU-wake fix (HOOK_AUDIT: BORDERLINE).
  - Flags: `--stl-ann-file`, `--stl-store-stall-cycles N`, `--stl-alias-pred {no_alias,alias,off}`.
  - Schemes as on recon-modded.
  - Run config: `runconfigs/run_config_STT_6_stl.jsonc` (scheme 2, hold 5000, `no_alias`, fnc 150).
- **Every other build needs a port:** `gem5-hooks/stl/apply_stl_hooks.py <gem5_root>` plus a rebuild (needs Anna's OK).

**Checker: there is no STL window checker yet.** check_ld / check_br verdicts mean nothing on STL tests (there is no `lc`, and `fnc` is the store), so full STL sweeps are blocked. Until it exists, `gem5-hooks/stl/stl_hooktest.py` scores them.

| eval row | STL in its threat model? | STL model family | can it run today? |
|---|---|---|---|
| E1 Unsafe | control | STT_6_stl | yes, on `gem5-recon-stl --scheme=0` (used as the control in the hook test) |
| E2 STT Kaxiras | yes (`decode.cc:686-695`) | STT_6_stl | yes, on `gem5-recon-stl` (stale); no window checker |
| E3 STT upstream | no: no store shadows (`rob_impl.hh:444-495`); a bypass leak is expected by design | STT_6_stl only as a labelled control | no hooks |
| E4 STT AMuLeT (Futuristic) | yes (a store-load alias is a squash source under Futuristic) | STT_6_stl | no hooks |
| E6 ReCon | yes (runs on Recon-STT's shadow tracker) | Recon_6_stl (draft) | partly: ReCon mode on `gem5-recon-stl` is not verified |
| E8 NDA, E9 DoM, E10 Doppelganger | probably (same shadow tracker; not verified in code) | STT_6_stl | on `gem5-recon-stl --scheme=1/3` (+ `--address_prediction`), untested |
| E11 SPT (Spectre configs) | no (branch-only visibility point) | — (the Futuristic configs would use SPT_6_oneLP_stl, blocked) | no hooks |
| E12 InvisiSpec | Futuristic mode only (InvisiSpec Sec. IV Table I), which is the parity mode | STT_6_stl | no hooks |
| E13 CleanupSpec, E14 SpecLFB | yes (CleanupSpec Sec. 2.1; SpecLFB Sec. 5) | STT_6_stl | no hooks |
| E7 OTB | n/a (two-source merge shape) | — | — |

**STL experiments done:**
- Hook test, 60 `STT_6_stl` tests on `gem5-recon-stl` (2026-10-30): 58/60 valid bypasses. STT sent 0/28 load transmitters in the window vs Unsafe 28/28; the `alias` and hold-0 controls gave 0 (`results/STT_6_stl_hooktest/controls/`).
- Shadows store-only + alias (2026-11-07): STT 0/32 vs Unsafe 32/32 (`results/STT_6_shadows_draft/`).

**Not done:** a full STL sweep (needs the checker), Recon_6_stl, schemes 1/3, and anything on the AMuLeT builds or gem5-spt (needs the port).

**STL this round (decided 2026-11-08, Anna): the Kaxiras-group builds only.**
- Rebuild `/work/gem5-recon-stl` from today's `gem5-recon-modded`, which adds the resolve hooks.
- Write the STL window checker.
- That covers E1, E2, E6, E8, E9 and E10.
- No port to the AMuLeT builds or gem5-spt this round. Not started.

## Decisions that change this manifest

- **Decided 2026-11-08:**
  - RI-only cores (re-derive the STT_6/Recon_6 drafts);
  - STL on the Kaxiras-group builds (rebuild `gem5-recon-stl` + STL checker);
  - SPT seed fix after the check, with sign-off;
  - Alloy on cafe2.
- **Still open:** clause-by-clause approval of every core draft.
- **Stage 1.5:** build and parallelize it (owned by Anna's Alloy agent). Then regenerate all testsets, ideally on the cafe2 container once `run_stage1.py`'s two Mac paths are configurable.
- **SPT:** sign off the seed diff (after the check) and decide P1-P5 before the regeneration.
- **STL:**
  - the window checker's design (`STL_SPECULATION.md`);
  - approve `Recon_6_stl`;
  - SPT STL's RS rule: exempt the alias location (recommended by stl-spec), drop RS, or skip SPT STL;
  - `rf` vs atom alias fact;
  - `STT_6_shadows`;
  - whether the forced memory-dependence prediction counts as "the predictor".
- **E4:** the config-glue edit (P-4). Anna wants every STT run separately, so dropping E4 is off the table.
- **AMuLeT parity:** P-1..P-5, the CleanupSpec TBE value, and which reference counts as "the defense's configuration" (`HOOK_AUDIT.md`; `wiki/findings/audits/2026-10-28/full_configs.md`). Also the needsTSO / Ruby / latency items for E3 and E11.
- **E7:** how OTB tests are produced. **E8-E10:** write NDA / DoM / Doppelganger defense blocks, or run STT_6 and say so.
