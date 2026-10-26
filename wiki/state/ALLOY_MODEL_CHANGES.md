# Pending Alloy model changes (owner-gated) — block out known-issue false positives

*Living doc, overwrite-in-place. The single consolidated list of `.als` edits we've concluded we
need, each one grounded in a findings doc. **Nothing here is applied** — every `.als`/`parsexml.py`
edit needs Anna's explicit per-change sign-off (root `CLAUDE.md` → Alloy models STRICT). This file is
the backlog + rationale so the edits don't live only in scattered findings mds.*

**Last refreshed:** 2026-10-26

---

## Why this exists

We triaged a wave of gem5 "hits" on STT and SPT, confirmed they were **model over-approximations /
concretization artifacts (not real leaks)**, and wrapped each up as a known issue with a findings doc.
Right now we only *mask* them (per-run diagnostics) or re-run after a checker fix. The durable fix is at
**Stage 1 (the `.als` model)**: stop the model from *emitting* these shapes, so future enumerations
don't regenerate false positives we then have to re-triage. These are the edits to do that — plus the
coverage edits for the bug classes the model structurally *can't* emit today.

**Rerun reality (why Anna flagged this):** every item in §A/§B is a Stage-1 change → the affected
testset must be **regenerated from `xml` onward** (`--force` on `xml`), and every build re-swept against
it. We have already re-run STT_6 and SPT_6_oneLP once for checker/diagnostic reasons; applying the
model fixes means **another full STT + SPT regen + re-sweep**. Batch the `.als` edits so we pay that
regen cost once, not per-fix. See the rerun matrix at the bottom.

---

## A. Block-out fixes — suppress the known false-positive shapes

These are the edits Anna asked for: stop the model generating the artifacts we've already dismissed.

### A1. Protection-set over-approximation → source-derived taint closure  ★ highest priority
**Blocks out:** the const-address `ld` false positives (~99.9% of SPT `ld` hits) **and** the SPT-Fence
`no_hold` false positives (64/64 harmless over-approximations) — same root cause.
**Source docs:** [`../findings/mdsToRead/POTENTIAL_MODEL_FIX_constaddr_taint.md`](../findings/mdsToRead/POTENTIAL_MODEL_FIX_constaddr_taint.md),
[`../findings/mdsToRead/SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md`](../findings/mdsToRead/SPT_FENCE_NO_HOLD_HITS_NOT_BUGS.md).
**Models:** `SPT_6_oneLP.als`, `SPT_6.als`, and the `STT_*` models that share the policy.

**Root cause:** `hardware_protection_policy` seeds the protection set with *essentially all operands*
(only excluding `Inreg`/`Inaddr` with **no** rf edge at all), then propagates forward. Net effect: **any
value produced under speculation is treated as secret** — even a register written by a speculative ALU
op reading only constants, or a load-fed address whose producer is itself safe. The real STT/SPT defense
only protects values *derived (by data flow) from a speculative load / memory read*.

**The fix (semantics):** make the protection set a **forward closure with union (OR) semantics** whose
**sources are load outputs (`Loads.outreg`) + read memory only** — NOT "all operands", NOT gated on
commit/speculation status:
1. **Sources** = `Loads.outreg` + read memory (+ last-committed protected memory if modeled).
2. **Propagate** = forward closure over `ddi`+`rf`; an operand is protected iff ≥1 input is protected.
3. **Union, never AND.**

**Consequences (the validation criterion):**
- Constant / const-ALU-address outputs fall out automatically (no load in their cone) → **const-addr
  FPs gone**, and the `no_hold` cases where the producer is safe/unspecified drop out too.
- **Load outputs stay tainted** (a load output is always a source) → load→load address chains stay
  protected. These are genuine signal — do **NOT** untaint them.
- Untaint of a load output happens **only** via clause-5 STLF-from-untainted-store. "Safe / committed /
  pre-branch" is **NOT** a valid untaint reason — see the doc's §6b (a wrong earlier draft, deleted).
- The `oneLP` STLF-subtraction hack (line ~350) likely becomes redundant and can be removed.

**Anchors to change (verify in the analyzer first — line numbers drift):** `hardware_protection_policy`
(~337/341), the `a[]`/`last_committed_protset_p` propagation (~222–236), `leakage_function` (~339,
optional), `one_insecure_speculation_scheme_p` (~268, shape unchanged — becomes correct once protset is
source-derived).

### A2. `rf` not constrained to the most-recent writer → clobber  ★ highest priority
**Blocks out:** the load→load `reached_cache` false positives — **~58.6% of the `SPT_6_oneLP` testset is
clobber-shaped**, so this is broad contamination, not an edge case. Supersedes the "19 = genuine
model-vs-gem5 signal" line in the const-addr doc: those are this rf bug, not real leaks.
**Source doc:** [`../findings/mdsToRead/ALLOY_RF_LASTWRITER_BUG.md`](../findings/mdsToRead/ALLOY_RF_LASTWRITER_BUG.md).
**Models:** all 17 that share the `rf` facts — `grep -l "fact same_state_rf" STAGE1_alloy/models/*.als`
(all `STT_*`, `SPT_6*`, `Recon_6`, …).

**Root cause:** `rf` only requires producer and consumer to **share a state** (`same_state_rf`) and the
consumer to have ≤1 producer (`one_entering_rf`); nothing forbids a state from having **two writers** or
forbids `rf` routing from an *older* writer **past a newer same-state writer**. After concretization
(one state → one register) the newer write clobbers the register, the consumer reads the wrong value,
and the program that runs isn't the one the model reasoned about.

**The fix (Option A — chosen; it's how real hardware behaves, reuse is legal):** forbid an intervening
same-state writer between an rf producer and its consumer:
```alloy
fact rf_from_most_recent_writer {
  all prod: Instruction.outs, use: prod.rf |
    no other: (Instruction.outs - prod) |
        other.opstate = prod.opstate
        and (prod.(~operands))  -> (other.(~operands)) in ^spo   // prod  before other
        and (other.(~operands)) -> (use.(~operands))   in ^spo   // other before use
}
```
Covers memory too (intervening store clobbering a load store-forward). **Validated on a copy** (no real
`.als` touched): still SAT, 150/150 enumerate; clobbered edges 1/150 → 0/150.
*(Rejected — Option B single-writer-per-state: forbids all register reuse, unrepresentative.)*

---

## B. Coverage changes — emit the bug classes the model structurally can't today

Not "block out" (these *add* signal), but the other half of the Alloy-edit backlog and worth batching
into the same regen. **Source docs:**
[`../findings/mdsToRead/ENUMERATION_OVERSPECIFICATION.md`](../findings/mdsToRead/ENUMERATION_OVERSPECIFICATION.md),
[`../findings/mdsToRead/OTB_GENERATION_GAP.md`](../findings/mdsToRead/OTB_GENERATION_GAP.md).

Measured problem: 100k STT_6 tests collapse to **~47 leak-cores, 98% a single `load→transmitter`
shape**, in-degree 1 — less leak-mechanism diversity than random. Over-constrained where it hurts,
under-constrained where it wastes.

- **B1. Diversity-driven enumeration** (highest leverage, *no semantics change*). Stop taking the
  solver's simplest-first 100k; enumerate by leak-core skeleton with blocking clauses. Lives in the
  **driver** `STAGE1_alloy/a6DiverseModels.java` (**built**) — not a `.als` edit, so no model
  approval needed, but it changes what a testset contains → still a regen.
- **B2. Relax per-branch minimality to joint.** `gen_useful_litmus` demands each unresolved branch be
  *individually* necessary → structurally forbids multi-source / multi-branch leaks (OTB /
  getOldestTaint / pending-squash class). Replace with a joint notion. Prototyped in
  `STAGE1_alloy/models/STT_6_multisource.als` (**built**; SAT-proven to unlock the class). **Needs B1 to
  actually surface the shapes** (relaxing the predicate enlarges the space; enumeration order still
  returns trivial witnesses first).
- **B3. Instruction-minimality / separate padding.** Add an `RI`-minimality clause, or enumerate cores
  first and cap padding separately, so the budget isn't burned on filler permutations.
- **B4. Variable / longer length.** Sweep instruction count instead of `exactly 6`; only useful after
  B1–B3 (else it just adds padding).
- **B5. Extend transmitter/edge vocabulary** (each its own owner-gated extension): store-address
  transmitter (→KV3), control-dependence `cdep` edge (→implicit flow), split/misaligned concretization
  flag (→UV4), fetch-path transmitter (→KV1).

---

## C. NOT Alloy edits — recorded so they're not re-opened as model changes

- **`check_br` squash-tick false positives** (STT br_x "leaks"). This was a **checker** bug, **already
  fixed** in `STAGE3_gem5/check_br.py` + `gem5_common.py` (key the verdict on the squash-broadcast tick,
  not the resolve/complete tick). STT's branch defense holds; the hits were FPs. **Not** a model or gem5
  bug, does not change relaunch scope.
  Source: [`../findings/mdsToRead/STT_BRANCH_LEAK_ROOTCAUSE.md`](../findings/mdsToRead/STT_BRANCH_LEAK_ROOTCAUSE.md).
- **Duplicate-PC Stage-2 codegen bug** — pipeline/codegen, not Alloy (see `claudelog.md`).
- **`check_br` lc/fnc-window gap** — checker, not Alloy (see `CLAUDE.md` → Leak criteria).

---

## Rerun matrix (what a batched apply costs)

| defense | model (latest) | A1 protset | A2 rf | regen scope | builds to re-sweep |
|---|---|---|---|---|---|
| **STT** | `STT_6` | ✅ (shared policy) | ✅ (shared rf) | `xml`→all, `--force` | stt, gem5-recon(`--scheme 2`), amulet-STT |
| **SPT** | `SPT_6_oneLP` (+ `SPT_6`) | ✅ | ✅ | `xml`→all, `--force` | gem5-spt (fence + invisispec variants) |
| **Recon** | `Recon_6` | policy shared? verify | ✅ | `xml`→all, `--force` | gem5-recon (`--scheme` 1/2/3) |

**Order of operations when Anna signs off:** (1) land A1 + A2 (+ B1 driver) together in each model so
one regen covers them; (2) `pipeline.py xml --force` to re-enumerate; (3) re-sweep each build via
`testrun.py`; (4) re-triage — the const-addr / no_hold / clobber diagnostics should now bucket **0** (if
they still match, the `.als` edit didn't fully land). Log the regen + contamination scope in
`claudelog.md` (per `CLAUDE.md` → "any reason a sweep had to restart").

**Before any edit:** show Anna the diff and wait (root `CLAUDE.md`). Re-verify every cited line number
in the Alloy analyzer — the docs warn the anchors drift.
