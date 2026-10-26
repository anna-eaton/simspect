# Minimality predicate: prune "tag-along" unresolved branches without re-forbidding multi-source leaks

> **⛔ PROPOSAL ONLY — owner sign-off required. No `.als` was touched.** Everything below was derived by
> *reading* the canonical models and by running probes on **throwaway copies in a scratch dir** (never in
> `STAGE1_alloy/models/`). Per root `CLAUDE.md` (Alloy models STRICT) every `.als` edit needs Anna's explicit
> per-change approval. This doc is the design + evidence so the edit can be reviewed, not applied.

**For:** Anna · **Date:** 2026-10-26 · session `session_014m8EvwkYaUmfWAHi9sqtF4`
**Scope of this doc:** the **minimality predicate** inside `gen_useful_litmus` only. The separate problem of
**reaching UNSAT instead of cutting off at the `max_instances` cap** (enumeration *completeness*) is being
handled by a companion effort — see `OTB_GENERATION_GAP.md` / `ENUMERATION_OVERSPECIFICATION.md` (axis #1,
the diversity driver). Cross-refs: `wiki/state/ALLOY_MODEL_CHANGES.md` **item B2**, `ENUMERATION_OVERSPECIFICATION.md`.

---

## TL;DR / recommendation

1. **The aggregate prototype's "sufficiency" clause is a tautology.** `secure_speculation_scheme_p[RR->unresolved]`
   (STT_6_multisource.als:320) is **always true** — resolving *all* unresolved branches leaves no speculation
   contract, so nothing is a speculative transmitter, so "secure" holds vacuously. **Empirically confirmed:
   0 counter-models** (probe P_TAUT below). So the prototype did not replace per-branch minimality with a
   weaker-but-real constraint; it replaced it with **no constraint at all**. That is *why* tag-alongs survive.

2. **Recommended change:** replace the per-branch clause with a **per-element necessity (irredundancy)** clause
   and **drop** the tautological aggregate:
   ```alloy
   all i: (unresolved - first_uncommitted) | not secure_speculation_scheme_p[RR->(unresolved - i)]
   ```
   Read: *"for every unresolved branch i, resolving everything-except-i must still leak"* ⟺ *"i, on its own,
   sustains a leak"* ⟺ *"i is load-bearing."* This **prunes pure tag-alongs** (a branch that sustains nothing
   is rejected) while **admitting** the multi-source / OTB-precursor shapes that the current per-branch clause
   forbids. Empirically: it **rejects** the exact tag-along instances the aggregate **admits** (P_C2_TAGALONG =
   0 vs P_AGG_TAGALONG = 2).

3. **Important honesty caveat (do not skip — it changes how you read "jointly-necessary").** Because `spo` is a
   **total order** (`fact spo_total`) and both *speculative-ness* and *secrecy* are governed by the **earliest
   unresolved branch**, resolving a *non-earliest* branch is a **no-op** for `secure` in STT_6 / Recon_6 (and
   for SPT under RR-only perturbation). Consequence: there is **no leak in which two branches are each uniquely
   necessary to secure** — the earlier branch always subsumes the later. So the necessity clause does **not**
   admit "genuinely jointly-necessary" branches (there are none); what it admits is **"each branch independently
   sustains a (possibly subsumed) leak"**, i.e. the **redundant-co-gate / 2-loads-under-2-branches OTB-precursor
   shape**. That shape is exactly what we want for **downstream-defense coverage** (getOldestTaint), even though
   the conservative Alloy oracle regards one of its branches as redundant. The predicate cannot tell an OTB
   merge from a redundant co-gate (they are `secure`-indistinguishable); it *can* tell either from a **pure
   tag-along** (a branch that sustains nothing). Pruning pure tag-alongs is the achievable, correct goal — and
   the necessity clause achieves it. See §2 and §4. **Empirically (P_C2_2BR, §7): at the production scope
   `exactly 6 Instruction`, both C1 and C2 are confined to ≤1 unresolved branch — the 2-branch OTB shape is
   UNSAT at 6. So at that scope C2's payoff is tag-along pruning + canonicalisation only; the actual multi-source
   coverage is gated on larger scope + `interleave`, with C2 as the predicate that (unlike C1) won't re-forbid
   it.** That is the sharpened bottom line.

4. **State analogue (clause `all s: State | secure_speculation_scheme_p[RS->s]`):** same structure, same
   aggregate-tautology trap, but states are **not** spo-ordered, so genuine multi-secret necessity is *more*
   plausible there. Apply the same necessity transform for consistency (§5) — a separate owner decision.

---

## 1. The problem, precisely

### 1.1 The current clause (per-branch necessity)

Canonical STT_6 (`STAGE1_alloy/models/STT_6.als:301`–`311`):
```alloy
let gen_useful_litmus {
  not secure_speculation_scheme_p[no_p]                                         // (a) it leaks
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i] // (b) per-branch necessity
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]   // (c) commit-boundary necessity
  all s: State | secure_speculation_scheme_p[RS->s]                            // (d) per-state necessity
}
```
Clause **(b)** demands that **resolving any single unresolved branch `i`, by itself, makes the whole program
secure** (`secure[RR->i]`). Equivalently: *every* unresolved branch must be a **universal cut** that kills
*all* leakage. The semantics that make this strong (`secure_speculation_scheme_p` at STT_6.als:262–265;
`speculation_contract_p = uncommitted_p & has_unresolved_brs_p` at :325; `has_unresolved_brs_p` at :245–247):
a transmitter is "speculative" iff it is spo-after **≥1** unresolved branch.

**Why (b) forbids multi-source.** If a transmitter is fed under *two* branches (or two transmitters sit under
two branches), resolving **one** of them leaves the leak alive via the other → `secure[RR->i]` is **false** for
that `i` → (b) is violated → the instance is pruned. This is the measured `99.6% in-degree-1 / single-source`
collapse (`ENUMERATION_OVERSPECIFICATION.md`). (b) also silently **canonicalises non-branch resolvedness**:
for a non-branch `i`, resolving it changes nothing in `secure` — see §2 — so `secure[RR->i] = secure[no_p] =
insecure`, which violates (b); hence (b) forces every unresolved **non-branch** to be marked resolved.

### 1.2 The aggregate relaxation and why it fails — it is a *tautology*

The prototype `STAGE1_alloy/models/STT_6_multisource.als:315`–`333` keeps (a),(c),(d) and replaces (b) with the
**aggregate** form (:320):
```alloy
secure_speculation_scheme_p[RR->unresolved]     // "resolving ALL unresolved speculation secures it"
```
**This constrains nothing.** Resolve *all* unresolved instructions and `unresolved_p = {}`
(`unresolved_p[p] = unresolved - p[RR] - p[RI]`, STT_6.als:207), so `has_unresolved_brs_p = {}` (:245–247),
so `speculation_contract_p = {}` (:325), so `speculative_xmit_p = {}` (:229), so **both conjuncts of
`secure_speculation_scheme_p` are `no (… & {}) = no {} = true`.** The clause is a theorem — it holds for *every*
instance, regardless of any tag-along branch.
*(The "leak is genuinely speculative" guarantee that this clause looks like it provides is actually already
supplied by clause (a): `not secure[no_p]` forces `speculative_xmit_p[no_p] ≠ {}`, hence ≥1 unresolved branch.)*

- **Empirically confirmed (P_TAUT):** `run { not secure_speculation_scheme_p[RR->unresolved] }` at the
  production scope returns **Total models: 0** — there is no 6-instruction model in which resolving all
  unresolved branches is insecure. Tautology. (The tautology relies on the **branch-only** speculation contract
  `uncommitted_p & has_unresolved_brs_p`; all canonical models use that form, so it holds for all of them. The
  commented alternative `… & (no_unresolved_brs_p + no_unresolved_mem_p)` would break it — not in use anywhere.)

So Anna's diagnosis is exactly right, and sharper than "the aggregate is too weak": **the aggregate is
vacuously true, so it removes per-branch minimality entirely.** Nothing prunes junk unresolved branches, and
nothing re-canonicalises non-branch resolvedness either.

### 1.3 Tag-along failure mode worked through on a concrete, *generated* shape

Probe **P_AGG_TAGALONG** (aggregate model + `#(unresolved & branches) ≥ 2` + "some unresolved branch is a
tag-along") is **SAT (2 models)**. Witness `inst-000001` (decoded from the Alloy XML; order by `idx`, IX0 =
first in spo):

| spo pos | instruction | kind | resolved? | committed? | role |
|---|---|---|---|---|---|
| IX0 | Instruction$4 | `TBranchn` | ✅ resolved | ✅ committed | prefix |
| IX1 | Instruction$3 | `TBranchn` | ❌ **unresolved** | — | **load-bearing branch** |
| IX2 | Instruction$2 | `TLoad`   | ❌ unresolved | — | (spurious unresolved non-branch) |
| IX3 | Instruction$1 | `TStore`  | ❌ unresolved | — | (spurious unresolved non-branch) |
| IX4 | Instruction$0 | `TBranchx`| ✅ resolved | — | **the transmitter** (`isxm`; `leakage_function` = `Branchxs.inreg`) |
| IX5 | Instruction$5 | `TBranchn` | ❌ **unresolved** | — | **TAG-ALONG** |

Two unresolved branches: **IX1** (before the transmitter IX4 → makes it speculative → load-bearing) and
**IX5** (the **last** instruction, spo-*after* the transmitter → gates nothing). Work the necessity test on IX5:
resolve everything except IX5 ⇒ the only unresolved branch is IX5, nothing is spo-after it ⇒
`has_unresolved_brs_p = {}` ⇒ **secure**. So IX5 contributes nothing, yet the aggregate keeps it (resolving the
*whole* set is secure no matter what IX5 does). **This is the tag-along.** (The unresolved `TLoad`/`TStore` at
IX2/IX3 are the *second* flavour of junk the aggregate re-admits: spurious unresolved non-branches that (b) used
to canonicalise away.)

---

## 2. The structural fact that reframes "jointly-necessary" (read before §3)

`spo` is a **total order** (`fact spo_total` STT_6.als:131; `total[spo,Instruction]` :181–184) — programs are
linear. In STT_6 and Recon_6, **both** relevant notions are governed by the **earliest unresolved branch**:

- **Speculative-ness:** `has_unresolved_brs_p[p] = (unresolved_p[p] & (Branchxs+Branchns)).(^spo_p)` (:245–247)
  — everything spo-after *any* unresolved branch. The earliest unresolved branch already covers all of them.
- **Secrecy:** `prot_set_propagation_p` removes a load's memory from the protection set iff the load has
  **no unresolved branch before it** (`no_unresolved_brs_bf_or_is_p`, STT_6.als:254–256, :329–332) — again a
  function of the earliest unresolved branch before each load.

**Therefore, resolving a *non-earliest* unresolved branch B (while an earlier A stays unresolved) changes
nothing:** every instruction after B is also after A (total order ⇒ A<B ⇒ everything after B is after A), so
no transmitter leaves `has_unresolved_brs_p`, and no load changes speculative status, so the protection set is
unchanged. `secure[RR->B] = secure[no_p]`. Two corollaries:

1. **The current per-branch clause (b) effectively forces ≤1 unresolved branch** (beyond `first_uncommitted`):
   any second unresolved branch is non-earliest, so `secure[RR->that] = secure[no_p] = insecure`, violating (b).
   This is an *additional* driver of the single-source collapse, on top of the dataflow-in-degree story in
   `ENUMERATION_OVERSPECIFICATION.md`.
2. **No two branches are each uniquely necessary to secure.** For a later branch B to be load-bearing-for-
   securing, resolving B would have to de-leak some transmitter; but any transmitter after B is after the
   earlier A and stays leaking. So **genuinely jointly-necessary multi-branch leaks do not exist** in these
   models. What *does* exist, and what we want for coverage, is the **redundant co-gate**: two branches each
   independently *sustaining* a leak, where the earlier subsumes the later (e.g. the OTB merge
   `A < ld1 < B < ld2 < other=f(ld1,ld2) < xm` — with only A unresolved the whole thing leaks; with only B
   unresolved it still leaks via `ld2`; so each branch *sustains* a leak, but A subsumes B).

**Why this matters for the fix.** No predicate built from the *conservative, monotone* `secure` oracle can
distinguish an OTB merge (**want**, for downstream getOldestTaint coverage) from a plain redundant co-gate
(**don't especially want**, non-minimal) — they present identically (resolving the earlier branch alone does not
secure; each branch alone sustains a leak). The achievable, well-defined goal is therefore: **prune branches
that sustain *nothing* (pure tag-alongs), keep branches that sustain *something* (co-gates, incl. OTB).** The
necessity clause in §3 does exactly that. The findings-doc phrase "jointly-necessary unresolved branches"
should be read as **"each branch independently sustains a leak,"** not "both are needed to leak."

> SPT_6 / SPT_6_oneLP use a different, **operand-level forward-taint** protection set
> (`hardware_protection_policy = Instruction.operands`, SPT_6.als:329; `prot_set_propagation_p` :332–345 untaints
> via `ddi`/`rf`). Its *speculative-ness* still comes from `has_unresolved_brs_p` (earliest-dominated under RR),
> and its RR-dependence enters only through `nonspeculative_xmit_p`/`speculative_xmit_p`, so the "non-earliest
> branch resolve = no-op" property still holds under RR. Recon_6's `hardware_protection_policy` is itself
> perturbation-dependent (`Recon_6.als:316–318`) but is also monotone-securing under resolve. **Flagged for
> empirical reconfirmation per model** (the probes in §7 are written to run against any model).

---

## 3. Proposed predicate(s)

### 3.1 Recommended: per-element necessity (irredundancy), drop the tautology

**Variant-1 models** (those with the `first_uncommitted` exclusion + the commit-boundary clause — STT_6,
SPT_6_oneLP, Recon_6): keep (a),(c),(d); replace (b):
```alloy
let gen_useful_litmus {
  not secure_speculation_scheme_p[no_p]                                                       // (a) unchanged
  all i: (unresolved - first_uncommitted) | not secure_speculation_scheme_p[RR->(unresolved - i)]  // (b') NEW
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]                 // (c) unchanged
  all s: State | secure_speculation_scheme_p[RS->s]                                          // (d) see §5
}
```
**Variant-2 models** (no `first_uncommitted` exclusion, no boundary clause — SPT_6/SPT_6_full,
SPT_6_oneLP_noSTLF, STT_6_modified_protset): replace the single clause `all i: unresolved | secure[RR->i]` with
```alloy
  all i: unresolved | not secure_speculation_scheme_p[RR->(unresolved - i)]
```
Do **not** add back an aggregate `secure[RR->unresolved]` clause — it is a tautology (§1.2); keeping it only
confuses a future reader. (If you want it present as documentation, write it as a comment, not a conjunct.)

**Exact semantics.**
- `RR->(unresolved - i)` is a `PTag->univ` binding whose `RR` entry is the set `unresolved - {i}`
  (`p[RR] = RR.p = unresolved - i`; cf. how `resolved_p` reads `p[RR]`, STT_6.als:206–207). The parentheses
  are **load-bearing**: without them, `RR->unresolved - i` parses as `(RR->unresolved) - i`, which subtracts a
  unary `i` from a binary relation (wrong arity / empty), silently breaking the clause. Keep the parens.
- `secure_speculation_scheme_p[RR->(unresolved - i)]` evaluates "secure" in the world where **every unresolved
  instruction except `i` is resolved** — i.e. `i` is the sole remaining unresolved instruction. `not …` asserts
  that world **still leaks**, i.e. **`i` on its own sustains a leak** ⟺ `i` is load-bearing.
- The set we resolve, `unresolved - i`, deliberately includes `first_uncommitted` so the necessity test truly
  isolates `i`; the commit-boundary question for `first_uncommitted` remains handled by the untouched clause (c).

**Cost.** Same *shape* as the current (b): one `secure` evaluation per element of `unresolved - first_uncommitted`.
But each evaluation is on `RR->(unresolved - i)` (a derived set inside the quantifier) rather than the singleton
`RR->i`, which is heavier to translate. See §7 — this measurably slows the scope-6 solve and is the one real
adoption risk ("does it starve enumeration?").

### 3.2 Alternative to consider: the contribution form (already in the prototype as a comment)

`STT_6_multisource.als:331–333` carries a commented alternative:
```alloy
all i: (unresolved - first_uncommitted) | some (speculative_xmit_p[no_p] - speculative_xmit_p[RR->i])
```
Read: *"resolving i removes ≥1 speculative transmitter."* This also prunes pure tag-alongs and is cheaper
(singleton `RR->i`, no `unresolved - i`). **But it behaves like the current (b) for a single-transmitter OTB
merge** — resolving the earlier branch leaves the single transmitter still in `speculative_xmit` (it leaks via
the other source), so the difference set is empty and the branch is *rejected*. I.e. **the contribution form
re-forbids the single-transmitter OTB merge we are trying to admit.** Prefer the necessity form (3.1), which
keys on "does *i* alone sustain a leak" rather than "does resolving *i* remove a transmitter," and so keeps the
merge. (If you ever only care about *distinct-transmitter* multiplicity and want strict minimality, 3.2 is the
tool — but that is not the OTB coverage goal.)

### 3.3 If strict minimality of co-gates is also wanted (heavier, owner-gated)

To *additionally* prune redundant co-gates while *keeping* true OTB merges, the predicate must become
**dataflow-aware** — e.g. require each unresolved branch to gate a load that lies on a **distinct** rf/ddi path
into the transmitter (no single earlier branch's gated sources subsuming it). This is substantially more complex
and more expensive, and it bakes a dataflow notion into the minimality predicate. **Not recommended** unless the
redundant-co-gate volume turns out to be a problem in practice: those shapes *are* the OTB precursors, so
pruning them trades away the coverage B2 exists to add. Documented here only for completeness.

---

## 4. Proof-sketch / truth-table

Notation: `U` = set of unresolved branches in the instance; `sec(R) := secure_speculation_scheme_p[RR->R]`
(resolve the set `R`; the unresolved branches then become `U \ R`). Established facts:
`sec({}) = not(clause a) = leaks = FALSE`; `sec(U) = TRUE` (tautology, §1.2).
Clauses: **C1** (current) = `∀i∈U: sec({i})`; **AGG** (prototype) = `sec(U)`; **C2** (proposed) = `∀i∈U: ¬ sec(U\{i})`.

**Scenario A — single load-bearing branch, `U = {A}`.**
`sec({}) = F` (leaks), `sec({A}) = sec(U) = T`.
- C1: `sec({A}) = T` → **accept.**  C2: `¬sec(U\{A}) = ¬sec({}) = ¬F = T` → **accept.** (Both keep the base case.)

**Scenario B — pure tag-along, `U = {A, J}`** (A before the transmitter; J after it / gates nothing — the P_AGG
witness, IX1 & IX5):
`sec({}) = F`; `sec({A}) = ` resolve A, only J unresolved, J gates nothing ⇒ `T`;
`sec({J}) = ` resolve J, only A unresolved ⇒ A still leaks ⇒ `F`; `sec({A,J}) = T`.
- **C1:** needs `sec({A}) ∧ sec({J}) = T ∧ F = F` → **reject** ✔ (prunes J).
- **AGG:** `sec(U) = T` → **accept** ✘ (keeps J — the bug).
- **C2:** `¬sec(U\{A}) ∧ ¬sec(U\{J}) = ¬sec({J}) ∧ ¬sec({A}) = ¬F ∧ ¬T = T ∧ F = F` → **reject** ✔ (J fails:
  `¬sec({A}) = F`, because with only J unresolved it is secure ⇒ J sustains nothing).
  **→ C2 matches C1 on pruning the tag-along, which AGG fails to do.**

**Scenario C — redundant co-gate / OTB-merge precursor, `U = {A, B}`**, `A < … < B < …`, where each branch,
alone, sustains a leak but the earlier A subsumes B (§2):
`sec({}) = F`; `sec({A}) = ` resolve A, only B unresolved ⇒ still leaks ⇒ `F`; `sec({B}) = ` resolve B, only A
unresolved ⇒ still leaks (A subsumes) ⇒ `F`; `sec({A,B}) = T`.
- **C1:** `sec({A}) ∧ sec({B}) = F ∧ F = F` → **reject** ✘ (this is the multi-source amputation — blocks OTB
  coverage).
- **AGG:** `sec(U) = T` → **accept** ✔ (but for the vacuous reason; it accepts everything).
- **C2:** `¬sec(U\{A}) ∧ ¬sec(U\{B}) = ¬sec({B}) ∧ ¬sec({A}) = ¬F ∧ ¬F = T` → **accept** ✔ (each branch alone
  sustains a leak). **→ C2 admits the OTB-merge precursor that C1 forbids, without the vacuity of AGG.**

**Summary.** C2 = "accept iff every unresolved branch independently sustains a leak." It is **strictly more
permissive than C1** (accepts everything C1 does, plus the co-gate/OTB shapes in C) and **strictly stricter than
AGG** (rejects the pure tag-alongs AGG keeps, scenario B). It cannot separate C's OTB-merge from a non-OTB
redundant co-gate (both look identical to the `secure` oracle, §2) — but both are "each-branch-sustains-a-leak"
and neither is a *pure* tag-along, so keeping both is the intended behaviour for coverage.
**Scope caveat:** this truth-table is the predicate's *logical* behaviour. At the production scope `exactly 6
Instruction`, **scenario C is empirically vacuous** (P_C2_2BR = UNSAT, §7) — the 2-branch co-gate/OTB shape does
not fit in 6 instructions. The table governs what C2 *will* admit once the shape is reachable (larger scope +
`interleave`), not what exists at scope 6; at scope 6 only scenarios A and B occur, so C2 = "C1 minus the junk."

**Non-branch canonicalisation is preserved.** For an unresolved **non-branch** `i`, `U\{i}` leaves `i` the sole
unresolved instruction, which (being a non-branch) yields `has_unresolved_brs_p = {}` ⇒ `sec(U\{i}) = T` ⇒
`¬sec(U\{i}) = F` ⇒ C2 **rejects**. So C2 forbids spurious unresolved non-branches, exactly as (b) did (and as
AGG fails to do — the IX2/IX3 loads/stores in the §1.3 witness).

---

## 5. RS / state analogue

Clause **(d)** `all s: State | secure_speculation_scheme_p[RS->s]` (STT_6.als:310) is the **per-state** twin of
(b): each state atom must be individually necessary (removing it alone secures). It has the identical structure
and the identical traps:

- **Same multi-source amputation:** a transmitter fed by **two secrets** (two states merged) fails (d) —
  removing one state still leaks via the other — so multi-secret leaks are pruned, just as (b) prunes
  multi-branch.
- **Same aggregate tautology:** the naive relaxation `secure_speculation_scheme_p[RS->State]` (remove *all*
  states) is **also a theorem** — `o_p[RS->State] = i_p.operands :> (Operand - opstate.State) = {}` (every
  operand's opstate is in `State`; `o_p` def STT_6.als:214) ⇒ no operands ⇒ no transmitter ⇒ secure. So the
  aggregate would re-admit **tag-along states** (a secret that feeds nothing) and provide no pruning.
- **The necessity analogue** (recommended for consistency):
  ```alloy
  all s: State | not secure_speculation_scheme_p[RS->(State - s)]
  ```
  "removing every state except `s` still leaks" ⟺ "`s` on its own sustains a leak" ⟺ "`s` is a load-bearing
  secret." Prunes tag-along states, admits multi-secret merges.

**Key asymmetry vs branches (why this one may unlock *genuinely* distinct multiplicity):** states are **not**
spo-ordered, so the §2 "earliest dominates / later is a no-op" argument **does not apply to states**. Two
*distinct* secrets feeding two distinct transmitters can be genuinely, separately necessary. So relaxing (d) to
the necessity form is *more* likely to add real signal than relaxing (b) — and correspondingly deserves its own
empirical check (§7, probe P_STATE_*). **Recommendation:** transform (b) and (d) **together** for a consistent
"irredundant-set" minimality; but they are separable, and leaving (d) strict is the conservative option if Anna
wants to change one axis at a time.

---

## 6. Per-model line anchors (verify in the analyzer before editing — the docs warn anchors drift)

`grep -ln "gen_useful_litmus" STAGE1_alloy/models/*.als` → 19 models carry it. Two structural variants:

**Variant 1 — `(unresolved - first_uncommitted)` + commit-boundary clause (c).** Replace the per-branch line;
keep (c). The canonical ones:

| model | per-branch clause (b) → replace | boundary (c) keep | state (d) → §5 | leak clause (a) |
|---|---|---|---|---|
| `STT_6.als` | **:306** | :308 | :310 | `not secure…` :302 |
| `SPT_6_oneLP.als` | **:318** | :320 | :322 | `one_insecure…` **:314** (exactly-one-leak; def :268–273) |
| `Recon_6.als` | **:296** | :298 | :300 | `not secure…` :292 |
| `STT_6_pincommit.als` | :296 | :298 | :300 | :292 |

**Variant 2 — `all i: unresolved | secure[RR->i]`, NO `first_uncommitted`, NO boundary clause.** Replace the one
line (no (c) to keep):

| model | per-branch clause → replace | state (d) → §5 |
|---|---|---|
| `SPT_6.als`  (= `SPT_6_full.als`, a symlink) | **:309** | :311 |
| `SPT_6_oneLP_noSTLF.als` | **:317** | :319 |
| `STT_6_modified_protset.als` | :295 | :297 |

**Other carriers (not in the "canonical four", same transform applies — re-verify each):** `STT_2/3/4/5.als`,
`STT_4_new.als`, `STT_5_ld_xmit_only.als`, `LP-only-STT_3.als`, `STT_6_core.als` (**note:** already adds an
`RI`-minimality clause at :303 — the B3 direction; its (b) is :294/boundary :296/state :298),
`STT_6_multisource.als` (the aggregate prototype, :320). Symlinks `STT_all.als`, `STT_6_interleave.als` →
`STT_6.als`; `SPT_6_full.als` → `SPT_6.als` (edit the real target once).

**The canonical four the task named:** STT_6 (:306), SPT_6 (:309, variant 2 — note the structural difference
from the others), SPT_6_oneLP (:318), Recon_6 (:296).

---

## 7. Empirical validation (results + exact probes)

All probes were run on **throwaway copies** of `STT_6.als` in the session scratch dir via the repo's enumerator
`java -cp alloy6.jar:. a6CountModels <model.als> <out> <limit>` (which solves `getAllCommands().get(0)`), at the
production scope `for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool`. Java 17
(`/opt/homebrew/opt/openjdk@17/bin/java`) + `STAGE1_alloy/alloy6.jar` are present locally. To reproduce, make a
copy of the target `.als`, set its single `run` command to the probe below, and run the enumerator.

| probe | run command (first/only `run` in the copy) | expected | **result** |
|---|---|---|---|
| **P_TAUT** — is the aggregate a tautology? | `run { not secure_speculation_scheme_p[RR->unresolved] }` | 0 ⇒ tautology | **0 ✔ confirmed** |
| **P_BASE** — C1 sanity | C1 `gen_useful_litmus` | SAT | **5 (SAT) ✔** |
| **P_C2_TAGALONG** — does C2 forbid tag-alongs? | C2 `gen_useful_litmus` **and** `some i: ((unresolved & (Branchxs+Branchns)) - first_uncommitted) \| secure_speculation_scheme_p[RR->(unresolved - i)]` | 0 ⇒ forbids | **0 ✔ confirmed** |
| **P_AGG_TAGALONG** — does AGG admit them? | AGG `gen_useful_litmus` **and** `#(unresolved & (Branchxs+Branchns)) >= 2` **and** the same `some i:` tag-along conjunct | SAT ⇒ admits | **2 (SAT) ✔ confirmed** (witness decoded in §1.3) |
| **P_C2** — C2 plain sanity/count | C2 `gen_useful_litmus` | SAT | **5 (SAT) ✔** |
| **P_C2_2BR** — does C2 admit ≥2 unresolved branches at scope 6? | C2 `gen_useful_litmus` **and** `#(unresolved & (Branchxs+Branchns)) >= 2` | informative | **0 (UNSAT) ✔ confirmed** |
| **P_BASE_2BR** — does C1 force ≤1 unresolved branch? | C1 `gen_useful_litmus` **and** `#(unresolved & (Branchxs+Branchns)) >= 2` | 0 (per §2) | **0 — by entailment** (C1-accepted ⊆ C2-accepted + P_C2_2BR=0); direct UNSAT proof was still grinding at write time, not needed |

**All claims are now confirmed:** (1) the aggregate sufficiency clause is a tautology (P_TAUT=0); (2) C1 and C2
are both SAT and generate normally (P_BASE=5, P_C2=5); (3) **C2 rejects the exact tag-along class the aggregate
admits** (P_C2_TAGALONG=0 vs P_AGG_TAGALONG=2) — *that pair is the fix, demonstrated*; and (4) **neither C1 nor
C2 admits ≥2 unresolved branches at the production scope `exactly 6 Instruction`** (P_C2_2BR=0; P_BASE_2BR=0 by
entailment, since C1-accepted ⊆ C2-accepted per §4).

**What result (4) means — important, sharpens the recommendation.** At scope 6, swapping in C2 **does not by
itself produce any multi-branch / OTB-merge instance** — that shape is **UNSAT at exactly-6-instructions** (the
two branches + their two distinct secret sources + transmitter + the `one_xm`/`tag_xm`/state-min machinery do not
fit, which is also what §2's earliest-domination predicts). So at the current scope, **C2's entire practical
effect is tag-along pruning + non-branch-resolvedness canonicalisation** — it yields the *same ≤1-unresolved-
branch regime as C1*, just without the junk the aggregate re-admitted. **The multi-source/OTB coverage that B2
wants is therefore gated on *scope + interleave*, not on the predicate:** you need a larger instruction count
(the `IX6..` symmetry-breaking surgery noted in `ENUMERATION_OVERSPECIFICATION.md`) and/or `interleave.enabled`
(which injects the second load/chain at *concretisation*, not in the base Alloy instance — `OTB_GENERATION_GAP.md`).
C2 is still the correct predicate to pair with those, because — unlike C1 — it **will not re-forbid** the OTB shape
once scope/interleave make it reachable (§4 scenario C). But do not expect C2 alone to change the single-branch
corpus at scope 6.

**The one real adoption risk — cost / "does it starve enumeration?"** The C2 solve is materially heavier than
C1/AGG: P_C2_2BR (full C2 clause + force ≥2 branches) did **not** finish within a 420 s budget on the
~76k-variable / ~151k-clause CNF, whereas the structurally-similar C1/AGG probes finished in that window. The
`RR->(unresolved - i)` set inside the necessity quantifier is the culprit (a derived set re-evaluated per `i`,
each triggering a full protection-set fold), vs C1's cheap singleton `RR->i`. **Action for the owner before
100k-scale adoption:** benchmark end-to-end enumeration throughput (instances/sec for the first N) of C1 vs C2 on
a copy; if C2 is materially slower per instance it shrinks the testset reachable under a fixed time budget, to be
weighed against the (at scope 6, purely tag-along-pruning) minimality gain. The scratch copies `p_*.als` and
their outputs remain in the session scratch dir for re-runs.

---

## 8. Caveats, open questions, sign-off

- **PROPOSAL ONLY. No `.als` touched. Owner per-change sign-off required** before any edit (root `CLAUDE.md`,
  Alloy models STRICT). Show Anna the exact diff for each model and wait.
- **Predicate ≠ enumeration.** Even with C2, the simplest-first SAT order will still return trivial single-source
  witnesses first and fill the `max_instances` cap before reaching co-gate/OTB shapes (measured in
  `ENUMERATION_OVERSPECIFICATION.md` for the aggregate: first 400 instances still 100% single-source). **C2 is
  necessary but not sufficient for OTB coverage** — it must be paired with the diversity driver
  (`a6DiverseModels.java`, B1) and, for the real OTB merge, `interleave.enabled` (OTB_GENERATION_GAP.md). The
  "reach UNSAT instead of the cap" / completeness problem is **out of scope here** and handled separately.
- **"Jointly-necessary" is a misnomer for these models** (§2): due to total spo order + earliest-branch
  domination, no two branches are each uniquely necessary-to-secure; C2 admits "each-branch-sustains-a-leak"
  (co-gate/OTB) shapes. The companion findings docs' wording should be read in that light. The **state** axis
  (§5) is where genuinely-distinct multiplicity is actually plausible (states are unordered).
- **Per-model semantics vary** — Recon's `hardware_protection_policy` is perturbation-dependent (Recon_6.als:316),
  SPT uses operand-level forward taint (SPT_6.als:329–345), SPT_6_oneLP uses an **exactly-one-leak** clause
  (`one_insecure_speculation_scheme_p`, :314/:268). The tautology and tag-along results were proven on STT_6;
  **re-run P_TAUT / P_C2_TAGALONG / P_AGG_TAGALONG per model** before trusting the transform there (the probes
  are model-agnostic; just point the enumerator at a copy of each).
- **Regeneration cost:** this is a Stage-1 change ⇒ every affected testset must be regenerated from `xml` onward
  (`--force`) and every build re-swept — batch it with the other `ALLOY_MODEL_CHANGES.md` edits (A1 protset, A2
  rf, B1 driver) so the regen is paid once. See that doc's rerun matrix.
- **Cross-refs:** `wiki/state/ALLOY_MODEL_CHANGES.md` **B2** (this is the detailed design for it);
  `ENUMERATION_OVERSPECIFICATION.md` (the measured over-specification + the aggregate prototype log);
  `OTB_GENERATION_GAP.md` (the enumeration-cap half of the OTB story).
