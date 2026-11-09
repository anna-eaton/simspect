# Brief for the manifest agent: which SPT model to run, and the harness facts every row inherits (2026-11-08)

**Consolidated 2026-11-08 into [`../state/EVAL_MANIFEST.md`](../state/EVAL_MANIFEST.md) and `specs/defense_units.json` (simspect-c8); facts checked against the files. Delete once Anna has read the manifest.**

From the resolve-hooks session, for the agent that owns `wiki/state/EVAL_MANIFEST.md` and `specs/defense_units.json`. Apply the edits in §1 to both files together. This brief replaces `wiki/design/MANIFEST_BRIEF_twophase_and_SPT.md` (deleted 2026-11-08): its two-phase content is already in EVAL_MANIFEST, and its SPT model choice is superseded here.

## 0. TL;DR

- **SPT model: `STAGE1_alloy/models/SPT_6_oneLP_v2.als`** (sha256 `acb1f2e21e5e6c3b…`). It's a DRAFT until Anna signs off. The original `SPT_6_oneLP.als` (sha256 713d0904) is kept unchanged, for provenance.
- **SPT Stage-1 core: `STAGE1_alloy/models/proposed_twophase/SPT_6_oneLP_v2_core_ri.als`, RI-only.** That matches the 2026-11-08 decision (RI-only for every family; SPT joins once the seed fix is in, and v2 contains it).
- **Every existing SPT testset is pre-v2:** regenerate from v2.

## 1. Edits to make

1. **E11 (SPT), the two-stage SPT row, the "Alloy models" table, and `defense_units.json`** (SPT `eval` and `model_families`):
   - model `SPT_6_oneLP_v2` (draft);
   - Stage-1 core `SPT_6_oneLP_v2_core_ri.als`;
   - testset = the regeneration from v2;
   - status NOT RUN.
2. **"SPT protection seed" block in EVAL_MANIFEST:** replace the status with "included in v2 as change [v2-2]; audited correct, loses no instance (§3)".
3. **Mark as pre-v2 / provenance only:**
   - `SPT_6_oneLP.als`;
   - `proposed_twophase/SPT_6_oneLP_core.als` and `SPT_6_oneLP_core_conservative.als`;
   - `testsets_latest/SPT_6_oneLP`;
   - the Mac corpora `testsets/SPT_6_oneLP__twophase_draft*`.
4. **Other v2 cores, for the record:**
   - `proposed_twophase/SPT_6_oneLP_v2_core_conservative.als` (no RO/RI): the fallback;
   - `proposed_twophase/SPT_6_oneLP_v2_core.als` (RO+RI): not recommended. It gives 6 at `but 3`, but nothing within 15 min at `but 4`, and RO+RI was decided against anyway.
5. **E6 (ReCon):** add the open item "`Recon_6.als` lacks `rf_from_most_recent_writer`, the same skeleton gap v2 fixes for SPT (v2-1)". No Recon v2 was made.
6. **All run configs for the final batch:**
   - set `sample_fraction`. The templates `runconfigs/fixed_20261030/*_fixed_latest.jsonc` (E2, E3, E11) still say `0.02` from validation;
   - point `testset_dir`/`results_name` at the regenerated testsets.
7. **"Harness additions" text:** the harness state below (§4).
8. **`specs/alloy_models.json`:** the `SPT_6_oneLP_v2` entry exists (tier `variant`, DRAFT). Flip it to `production` when Anna approves.

## 2. What v2 changes

v2 is `SPT_6_oneLP.als` plus four edits, each marked `[v2-n]` in the file; every other line is byte-identical.

| | change | why | effect |
|---|---|---|---|
| v2-1 | add `rf_from_most_recent_writer`, verbatim from `STT_6.als:161-170` | the shared skeleton drifted: only STT_6 had it. In 68% of the old SPT testset an rf edge reads a register past a newer writer, so parsexml's program is not the instance (47% on the transmitter operand) | removes only instances no register machine can realize |
| v2-2 | protection seed over the perturbed program (simspect-c8 / twophase-spt fix) | the old seed ignored perturbations, so state/operand/instruction minimality could never shrink the protected set. That's why the SPT core was empty | adds instances, loses none (§3); makes SPT cores satisfiable |
| v2-3 | base clause `not secure_speculation_scheme_p[no_p]` (≥1 insecure transmitter) instead of `one_insecure_…` (exactly 1) | the skeleton form STT/Recon use; SPT alone pruned two-leaker tests | strictly adds instances; `xm` still names the one the checker scores |
| v2-4 | declassification removes the transmitted value and its producer (`.*(~rf_p)`), not its whole rf+ddi backward cone | SPT untaints backward only through MOV, and through invertible arithmetic when all but one input is public (paper §6 "Untaint rules"; gem5-spt `rob_impl.hh:853-878`). The old cone declassified values SPT still protects, so their leaks were never generated | the protection set is a superset of SPT's, so more tests. Some hits will be SPT legitimately untainting through a mov/add; the x86 slicer classifies those |

Not included, on purpose (Anna prefers too many tests): P3, which would drop the ~10% constant-derived transmitters, and P5, a skeleton-wide fact for unfed reads in all models. Both are in `wiki/state/ALLOY_MODEL_CHANGES.md`.

## 3. Evidence

Mac runs are in `results/spt_v2_20261108/`.

- **v2-2 audit (the other sessions' seed fix):**
  - It equals the old seed at `no_p`; their `eq_base` check is UNSAT.
  - It is a subset of the old seed under every perturbation.
  - The propagation is monotone (each subtracted term grows as the set shrinks), and so is `secure_*`. The non-monotone exactly-one clause is evaluated only at `no_p`.
  - So old-useful ⇒ new-useful.
  - Their log labels the base `sha 65eae944`; the file is 713d0904, unchanged. The label is wrong.
- **Satisfiable:** v2 gives 50 instances in 9 s, and 3,000 in 2 min, at `exactly 6`.
- **Shape census of 3,000 instances, old → v2** (`STAGE3_gem5/triage/spt_testset_shapes.py`):
  - stale rf 63% → 0;
  - clean 23% → 58%;
  - unfed read 28% → 33%;
  - constant-derived transmitter 2.4% → 9.6%.
- **Differential, both sides under v2's facts** (realizable instances only):
  - in both: ≥500 (capped);
  - gained by v2: ≥500 (capped). A census of 300 gained: 227 clean, 72 constant-derived, 1 unfed read.
- **Lost (old-useful and not v2-useful): still open.**
  - The Mac run found no counterexample in 90 min, then timed out.
  - An 8 h rerun is on cafe2, logging to `/tests/simspect_fixed_20261030/triage/spt_v2/lost_cafe2.log`.
  - Only v2-4 can lose an old instance, through minimality. v2-1 loses only unrealizable ones; v2-2 and v2-3 provably lose none.
- **Cores:**

  | core | `but 3` | `but 4` |
  |---|---|---|
  | RI-only (`v2_core_ri`) | 546 | 5,000 (capped) |
  | conservative (no RO/RI) | 546 | |
  | RO+RI | 6 | no result in 15 min |
  | old RO+RI core, for comparison | 0 | |

## 4. Harness state every row inherits

- **Resolve hooks, derived branch force, execution-validity gate** on all 8 hooked builds: `wiki/design/RESOLUTION_HOOKS.md`, `wiki/findings/bug/BRANCH_ANNOTATION_AND_FORCE.md`.
- **lc/fnc retire from the Commit trace** when O3PipeView lacks the record (`gem5_common.fill_retire_from_commit`, 2026-11-07). It's in the Mac repo and the cafe2 fixed copy (`/tests/simspect_fixed_20261030/`), **not in the shared `/tests/simspect` repo yet**: `make sync` before the final batch.

## 5. Known causes per row, so the final results aren't misread

These are from round 4 (2% sample, `results/*_fixed_latest__20261108_012818`, analyses in `/tests/simspect_fixed_20261030/triage/r4/`).

- **E2, STT Kaxiras (`gem5-recon-modded --scheme=2`):** 91 / 94 load tests hit. All 185 test×mode runs are the known real bug A2: a load the defense marks tainted and speculative takes data forwarded from a store and completes before the branch resolves. Classifier: `STAGE3_gem5/triage/recon_stlf_check.py` + `STAGE3_gem5/triage/diag/diag_recon_stlf_bypass.py`.
- **E3, STT upstream (`/work/stt`):** 0 hits (rounds 2 and 4).
- **E11, SPT** (round 4 ran the old model): all 341 hit tests were model or concretization artifacts. With v2, expect these to classify, not bugs:
  - constant-derived transmitters, ~10% of v2 instances;
  - hits made public by unfed reads (P5).

  Tools: `STAGE3_gem5/triage/spt_cond_slice.py`, `spt_taint_probe.py`, `diag/`.
- **E11, store transmitters (`str`):** no checker exists. They're scored by check_ld's fallback (the store's complete tick), so this is a blocker or decision for that kind.

## 6. Decisions to carry (Anna's)

1. Approve `SPT_6_oneLP_v2.als`, after the cafe2 "lost" check reports.
2. P3, drop the constant noise: proposed no.
3. P5, the skeleton-wide unfed-read fact (all models).
4. Give `Recon_6.als` the rf fact.
5. A criterion for store transmitters.
