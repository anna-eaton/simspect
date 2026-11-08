# Brief for the experiments-manifest agent — two-phase Alloy models + the SPT Stage-1 fix

**Consolidated 2026-11-08 into [`../state/EVAL_MANIFEST.md`](../state/EVAL_MANIFEST.md) (simspect-c8).** Two corrections made there: the cafe2 `gem5_dev` container does have Java 17 + `alloy6.jar` (only `run_stage1.py`'s paths are Mac-specific), and the perturbation-aware seed does not change SPT's leak semantics (unperturbed seed identical, differential check), so it is not the A1 rewrite. This brief can be deleted once Anna has read the manifest.

Hand this to the agent building the full experiments manifest. It records what changed 2026-11-07/08 (the SPT two-phase fix) so the manifest represents the Alloy models correctly. Full detail + reproducible evidence: `wiki/design/TWO_PHASE_MODELS.md` (sections "2026-11-07 — RESOLVED" and "2026-11-08 — conservative run done"), `claudelog.md` (2026-11-07/08 `twophase-spt`). Source of truth for canonical models: `specs/defense_units.json:4` `canonical_models = {STT: STT_6, SPT: SPT_6_oneLP, Recon: Recon_6}`.

## 0. Handoff from resolve-hooks (2026-11-08): SPT model and harness facts for the eval manifest

This supersedes the SPT model choice in §1–§2 and the "SPT protection seed" block in `wiki/state/EVAL_MANIFEST.md`. Apply the edits below to `EVAL_MANIFEST.md` and `specs/defense_units.json` together; `specs/alloy_models.json` already has the v2 entry.

### Edits to make

1. **SPT model family = `STAGE1_alloy/models/SPT_6_oneLP_v2.als`** (sha256 `db9ea73ab1bbb832…`, DRAFT until Anna signs off). Change it in: row E11, the two-stage SPT row, the "Alloy models" table and `defense_units.json` SPT `eval`/`model_families`.
   - **Stage-1 core: `proposed_twophase/SPT_6_oneLP_v2_core_ri.als` (RI-only).** That follows the 2026-11-08 decision "SPT moves to RI-only once the seed fix is signed off", because v2 contains the seed fix. 546 instances at `but 3`; it was made by `derive_core.py --minimality ri`.
   - Fallback: `SPT_6_oneLP_v2_core_conservative.als` (no RO/RI; also 546 at `but 3`).
   - `SPT_6_oneLP_v2_core.als` (RO+RI) gives 6 at `but 3` but nothing at `but 4` within 15 min. Don't use it; RO+RI was decided against anyway.
   - **Mark as pre-v2 (provenance only):**
     - `SPT_6_oneLP.als` (713d0904, kept unchanged);
     - `proposed_twophase/SPT_6_oneLP_core.als` and `SPT_6_oneLP_core_conservative.als`;
     - `testsets_latest/SPT_6_oneLP` and the `SPT_6_oneLP__twophase_draft*` corpora.
   - **"SPT protection seed" block:** it's now v2's change [v2-2], so replace the status. The audit says it's correct and loses nothing, by monotonicity: the seed is equal at `no_p`, a subset under every perturbation, and the propagation and `secure` are monotone. simspect-c8's "lost" check was still running at the time of writing; a 0 confirms it.
2. **What v2 changes** (put one line per change in the models table; the file marks each as `[v2-n]`):
   - **v2-1:** adds `rf_from_most_recent_writer`, copied from STT_6. Without it, in 68% of the old SPT testset the program isn't the instance.
   - **v2-2:** the perturbation-aware seed.
   - **v2-3:** requires ≥1 insecure transmitter, the skeleton's form, instead of exactly 1.
   - **v2-4:** declassifies only the transmitted value, not its whole backward cone (SPT paper §6; `rob_impl.hh:853-878`).

   Evidence:
   - Census of 3,000 instances, old → v2: stale rf 63% → 0, clean 23% → 58%.
   - Differential: ≥500 instances in both, ≥500 gained, 76% of the gained clean.
   - `results/spt_v2_20261108/`; `ALLOY_MODEL_CHANGES.md` 2026-11-08.
3. **Recon_6 row (E6):** `Recon_6.als` lacks the same `rf_from_most_recent_writer` fact. There's no v2 for Recon, so carry it as "Anna: give Recon_6 the rf fact?".
4. **Every row's run config: set `sample_fraction` for the final batch.** The templates `runconfigs/fixed_20261030/*_fixed_latest.jsonc` (E2, E3, E11) still have `sample_fraction: 0.02` from validation. Also point their `testset_dir`/`results_name` at the regenerated testsets.
5. **Harness state every row inherits** (add to "Harness additions"):
   - the resolve hooks, derived branch force and execution-validity gate on all 8 hooked builds (`wiki/design/RESOLUTION_HOOKS.md`);
   - lc/fnc retire taken from the Commit trace when O3PipeView lacks the record (`gem5_common.fill_retire_from_commit`, 2026-11-07).

   The second exists on the Mac and in the cafe2 fixed copy (`/tests/simspect_fixed_20261030/`), **not yet in the shared `/tests/simspect` repo**: run `make sync` before the final batch.
6. **Known causes per row, so the final results aren't misread** (round 4, 2% sample, `results/*_fixed_latest__20261108_012818`):
   - **E2 STT Kaxiras (recon-modded):** ld 91 / 94 tests. All 185 = the known real bug A2, store-to-load forwarding skipping the STT check. Classifier: `STAGE3_gem5/triage/recon_stlf_check.py` + `triage/diag/diag_recon_stlf_bypass.py`.
   - **E3 STT upstream:** 0 hits (rounds 2 and 4).
   - **E11 SPT** (round 4 ran the old model): all 341 hit tests were model or concretization artifacts. With v2, expect two kinds of noise to classify, not bugs (tools in `STAGE3_gem5/triage/`: `spt_cond_slice.py`, `spt_taint_probe.py`, `diag/`):
     - constant-derived transmitters (~10% of v2 instances; the optional fix P3 is deliberately left out);
     - declassified-by-unfed-read hits (a skeleton issue in every model, P5).
   - **E11 store transmitters (`str`):** no checker. They're scored by check_ld's fallback (the store's complete tick), so this is a blocker or decision for that kind.

### Decisions to carry (Anna's)

- Approve `SPT_6_oneLP_v2.als`.
- P3 (drop the constant noise): proposed no.
- P5 (skeleton-wide unfed-read fact).
- The rf fact for `Recon_6.als`.
- A store-transmitter criterion.

## 1. Every production model has a two-stage structure; represent both stages

The two-phase design: **Stage 1** enumerates seed "cores" (the `_core` files); **Stage 2** ("round 2") pins each core and only *adds* interleave/padding (RO/RI off, seed contains the skeleton). Stage 2 is **not built yet** for any defense — the manifest should mark round 2 as not-yet-constructed. The Stage-1 analogues are:

| Defense | Production model (Stage 2 base) | Stage-1 analogue (`_core`) | Stage-1 minimality | Stage-1 result |
|---|---|---|---|---|
| STT | `STT_6.als` | `STT_6_core.als` | RO+RI | 2 cores |
| Recon | `Recon_6.als` | `proposed_twophase/Recon_6_core.als` | RO+RI | 2 cores (≈ STT; reveal clause is a no-op, R-1) |
| SPT | ~~`SPT_6_oneLP.als`~~ → **`SPT_6_oneLP_v2.als` (see §0)** | ~~`SPT_6_oneLP_core_conservative.als`~~ → **`proposed_twophase/SPT_6_oneLP_v2_core_conservative.als`** | none (RO/RI off) | old core: 20000, CAPPED; v2 core: 546 at `but 3` |

The `_core`/analogue files are **not separate models** — they are the production model's defense block, byte-identical, with only the Stage-1 minimality + scope relaxation added (`proposed_twophase/derive_core.py`). All of these are **UNAPPROVED DRAFTS** (Anna signs off clause-by-clause before any production campaign or paper number).

## 2. SPT is the special case: RO+RI minimality is INCOMPATIBLE with SPT's model (true of the OLD model; v2's seed fix makes RO+RI SAT, see §0)

Do **not** assume all defenses share one Stage-1 recipe. Investigated 2026-11-08: for SPT, RO+RI minimality (and RI-only, and RO-only) each enumerate **0 instances**, while SPT base leaks are abundant. Root cause: SPT's protection seed `hardware_protection_policy` (`SPT_6_oneLP.als:341`) is defined over the **whole, unperturbed program** (`Instruction.operands`, `Instruction.outreg.rf`, no `[p]`), so removing an instruction/operand never shrinks the protected set → no leak is ever minimal → UNSAT. STT/Recon are fine because their seed is the `Mem_s` sig with all instruction-sensitivity in the *perturbed* propagation.

**Manifest implication:** record Stage-1 minimality **per defense**, not globally. SPT's Stage-1 = **conservative (no removal-minimality: base `one_insecure` + RR/RC/RS only, over-generate)**. This is strictly more conservative (its solution set is a superset of RO+RI's, which was empty), so **the conservative SPT core is the default SPT Stage-1 analogue** (Anna approved making it default, conditional on it being certainly more conservative — it is). The RO+RI `SPT_6_oneLP_core.als` is kept for provenance but is a dead end (0 instances); mark it superseded.

Note I did **not** rename files or edit any existing `.als` — the manifest should formalize "conservative = default SPT Stage-1." The real long-term fix (making the seed perturbation-aware — this is the A1 protection-set rework) is **parked**, needs Anna's sign-off, and would change SPT semantics; flag it as a known open item, not a blocker.

## 3. STL versions: include where applicable, and they also need special minimality

Include the STL variants per the other agent's scheme. STL is **not** uniform either: `STT_6_stl`'s RO+RI Stage-1 core is UNSAT by construction; **RI-only is SAT** (`TWO_PHASE_MODELS.md:24`). So STL, like SPT, needs its own Stage-1 minimality setting — don't copy STT_6's RO+RI blindly. STL applies to the STT-family builds (`/work/gem5-recon-stl`); confirm per-build applicability against `specs/defense_units.json` / `specs/gem5_builds.json`.

## 4. Status: mark everything NOT RUN

Anna is rerunning everything, so set all testsets/campaigns to **not run**. On-disk Stage-1 draft outputs that exist now (all **local on the Mac, not cafe**, gitignored): `testsets/STT_6__twophase_draft/` (2), `testsets/Recon_6__twophase_draft/` (2), `testsets/SPT_6_oneLP__twophase_draft_conservative/` (20000, capped). The old `testsets/SPT_6_oneLP__twophase_draft/` is the RO+RI dead-end (0) — mark superseded. These are Stage-1 draft corpora only; no Stage-2 (round 2) testsets exist yet, and nothing has been run through gem5.

## 5. Open items the manifest should carry (don't resolve silently)

- Stage 2 (pin + add) not built for any defense → the manifest's "two-stage" rows are Stage-1-only so far.
- SPT seed fix (A1 / perturbation-aware `hardware_protection_policy_p[p]`) — parked, needs approval; would let SPT use real minimality instead of over-generation.
- Where Alloy runs execute: currently **local** (`run_stage1.py:33` hardcodes the Mac's Homebrew Java). If the manifest assumes cafe for Alloy, that setup (Java + `alloy6.jar` in the `gem5_dev` container) does not exist yet.
- SPT Stage-1 over-generates (20000+ capped); if round-2 volume is unwieldy, a scope-ladder minimality for SPT is the smaller-but-still-conservative alternative.
