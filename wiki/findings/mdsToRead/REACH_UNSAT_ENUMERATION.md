# Reaching UNSAT: enumeration completeness for STT & SPT (replace the cap with a principled, terminating scheme)

> **STATUS: PROPOSAL / ANALYSIS ONLY.** No `.als` model and no Java driver was edited. All
> empirical numbers below were produced **this session** from *throwaway* scope-reduced copies in
> the scratchpad (the canonical `STT_6.als` / `SPT_6_oneLP.als` were only **read**). Every model /
> scope change recommended here is **owner-gated**; the driver changes are not (Java, not `.als`).
> Companion scope: the **joint-minimality tag-along predicate** (B2) is being handled by a separate
> agent — this doc is about **enumeration completeness** (reaching UNSAT), not the minimality predicate.

**For:** Anna — "have we ever reached unsat for the STT and SPT models. i want to get to unsat, i
dont want to just cut off. how to fix this problem. I need to clean up the act."
**Date:** 2026-10-26
**Cross-refs:** [`ENUMERATION_OVERSPECIFICATION.md`](ENUMERATION_OVERSPECIFICATION.md),
[`OTB_GENERATION_GAP.md`](OTB_GENERATION_GAP.md), [`STAGED_ENUMERATION.md`](STAGED_ENUMERATION.md),
[`../../state/ALLOY_MODEL_CHANGES.md`](../../state/ALLOY_MODEL_CHANGES.md) (items B1–B5 + rerun matrix),
[`../../state/DASHBOARD_PLAN.md`](../../state/DASHBOARD_PLAN.md) (§"reached unsat" signal).

---

## TL;DR

1. **Have we reached UNSAT for STT/SPT? NO** — never for a production testset. Every production run
   (`STT_6`, `SPT_6`, `SPT_6_oneLP`) **truncates at the `alloy.max_instances` cap** (100k or 5k); the
   enumerator stops at `count == cap`, not at UNSAT. The only driver that *can* report UNSAT
   (`a6DiverseModels.java`) has never actually reached it in a run — it stalls on a **performance
   wall** (~6 skeletons), not exhaustion. The lone historical exhaustion is a **different, older
   model at `exactly 3`** (`old/crap/STT_kind_all`, 6211 instances). I **did** reach UNSAT this
   session on the *current* models — but only at `exactly ≤3` (see table).
2. **Why the cutoff:** a hard cap **plus** simplest-first SAT order. `sol.next()` blocks only the
   exact previous full assignment and the solver returns structurally-smallest models first, so the
   cap fills with the two trivial `load→xmit`/`branchx` shapes long before any rare shape — and long
   before exhaustion.
3. **Finite? yes. Canonical? yes. Exhaustible at `exactly 6`? effectively no.** The space is a fixed
   finite bound and the symmetry-breaking already yields **canonical-unique** instances (verified:
   at `exactly 3`, raw solver count == `find_duplicates` count == 80, zero dups). But the count
   **explodes** with instruction count (STT: `N=3`→80, `N=4`→**>6,748 and not finished in 45 s**,
   `N=6`→**>100k**, the production cap). Flat exhaustion of `exactly 6` is intractable, so **"just
   remove the cap" is not the fix.**
4. **The clean scheme (recommended):** stop claiming completeness over the intractable full
   `exactly-6` space. Instead reach **real UNSAT over two tractable spaces**: (a) **staged exact
   bounds** `N=2,3,4,…` (UNSAT at each N = *provably complete for programs of that size*), and
   (b) **blocking-clause enumeration to UNSAT over the leak-core quotient** at `exactly 6`
   (`a6DiverseModels`, made incremental) = *every distinct leak mechanism*, not 100k permutations of
   two. Then flesh each exhausted core out with a *capped* number of concrete tests (capping padding
   is fine; capping the thing you want to be complete over is not). (a)+(b) are mostly **driver**
   work; variable length and minimality relaxations are **owner-gated** `.als` changes.

---

## 1. Have we ever reached UNSAT? (definitive, with evidence)

### 1.1 The production path stops at the cap, by construction

`pipeline.py` phase `xml` shells out to the Java enumerator:

```
# pipeline.py:117-123
max_inst = cfg.get("alloy", {}).get("max_instances", 100000)
cmd = ["java","-cp","alloy6.jar:.","a6CountModels", str(model_file), str(xml_dir), str(max_inst)]
```

`a6CountModels` stops at the **first** of {UNSAT, cap}:

```java
// a6CountModels.java:49
while (sol.satisfiable() && count < limit) { ... sol = sol.next(); }
```

`limit` is `alloy.max_instances` from the run config:

| model (config)                         | `max_instances` | scope (`.als` run) | reached UNSAT? |
|----------------------------------------|-----------------|--------------------|----------------|
| `STT_6` (`run_config_STT_6.jsonc:17`)  | **100000**      | `exactly 6` (STT_6.als:317) | **No — cap hit** |
| `SPT_6_oneLP` (`run_config_SPT_6_oneLP.jsonc:25`) | **100000** | `exactly 6` (SPT_6_oneLP.als:329) | **No — cap hit** |
| `SPT_6` / `SPT_6_full` (`run_config_SPT_6.jsonc:20`, `_full:24`) | **5000** / 100000 | `exactly 6` (SPT_6.als:316) | **No — cap hit** |
| SPT invisispec/fence variants          | **5000**        | `exactly 6`        | **No — cap hit** |

Every findings doc treats the corpus as the full capped size — "100,000 STT_6 tests"
(ENUMERATION_OVERSPECIFICATION.md:1,10), "exhaust the cap before any `other`-on-path instance"
(OTB_GENERATION_GAP.md:57-60), "streams … up to `alloy.max_instances=100000` … the 100k cap fills
with direct `load→xmit`" (METHODS_CONCRETIZATION.md:78-83). `DASHBOARD_PLAN.md:32-34,100-104` states
the completeness rule outright: **`count < cap` ⇒ exhausted (reached unsat); `count == cap` ⇒
incomplete** — and the whole dashboard treats these runs as the `count == cap` (red / incomplete)
case. Each model has exactly **one** `run` command (`gen_lit`), so `getAllCommands().get(0)` is
always the capped `gen_lit` enumeration — there is no second, exhaustive command hiding anywhere.

**Conclusion:** no production STT/SPT testset has ever reached UNSAT. They are all cap-truncations.

### 1.2 The one driver that can report UNSAT has never actually reached it

`a6DiverseModels.java` is the exception that proves the rule — it is explicitly written to terminate
at UNSAT:

```java
// a6DiverseModels.java:129-140
while (count < limit) {
  ... A4Solution sol = execute_command(...);
  if (!sol.satisfiable()) { System.out.println("UNSAT after " + count + " distinct skeletons"); break; }
  ... blocks.append(skeletonBlock(world, sol, (int) count));   // persistent blocking fact
}
```

But it blocks the **leak-core skeleton** (position-independent, atom-identity-free; :16-19, :67-107),
not full instances, and in practice it **never prints UNSAT** — it hits a **performance wall**: it
re-parses + re-translates the whole model every step (:130-131), so accumulated blocks make each
solve slower and a run "stalled past ~6 within the time budget"
(ENUMERATION_OVERSPECIFICATION.md:142-145, :159-160; claudelog.md:343, :351). So even here, the
UNSAT branch has not fired on a real run.

Likewise the staged core enumerator (`stage_pipeline.py` / `STT_6_core.als`) is **wall-clock
bounded** precisely because proving no-more-cores is too slow: "the timeout just stops the fruitless
exhaustion proof" (STAGED_ENUMERATION.md:44-45; claudelog.md:277-278). It found 2 cores; it did
**not** prove UNSAT.

### 1.3 Where UNSAT *has* been reached

- **This session, current models, small scopes** (my throwaway probe, §3): `exactly 2` → UNSAT at 0
  (no leak fits in two instructions); `exactly 3` → UNSAT at 80 (STT) / 194 (SPT). So the *current*
  models do terminate at UNSAT — just not at the production scope.
- **Historically, a different/older model:** `old/crap/STT_kind_all/` holds **6211** XMLs, matching
  the memory note "6211 unique instances … zero duplicates" for the **old** kind model
  (`STTcommittedsp_kind.als`) at `exactly 3 Instruction`. That enumeration terminated (a complete
  count), so it is the lone precedent of real exhaustion — but at `exactly 3` on a less-constrained
  ancestor, **not** today's `STT_6`/`SPT` at `exactly 6`.
- **Differential UNSAT probes** (sanity checks, not corpus runs) appear throughout the log — e.g.
  "base STT_6 → UNSAT by construction" for the multi-branch probe (ENUMERATION_OVERSPECIFICATION.md:105),
  "bug shape SAT→UNSAT" verifications (claudelog.md:1521,1524,1697). These confirm the solver returns
  UNSAT when a space is genuinely empty; they are not full-corpus exhaustions.

---

## 2. Why do we cut off? (the mechanism)

Two compounding causes:

**(1) The cap is a deliberate truncation, never an exhaustion.** `a6CountModels.java:49` halts at
`count < limit`. The default is tiny (`limit = 1000`, :31); configs raise it to 100k/5k. It was
designed as "give me up to N tests," not "enumerate the space." So on any model whose true count
exceeds the cap, the run ends at `count == cap` with the space nowhere near exhausted.

**(2) Simplest-first SAT order + per-model-only blocking means the cap fills with the trivial
shapes, far from exhaustion.** `sol.next()` (Kodkod) adds a blocking clause for **only the exact
previous full assignment**, and the SAT solver plus lex-leader symmetry-breaking
(`opt.symmetry = 80`, a6CountModels.java:41) emit **structurally-smallest models first**. So:
- the 100k cap fills with the two trivial `load→xmit` / `branchx` cores — measured **98% depth-1,
  47 distinct leak-cores, 99.6% in-degree-1** (ENUMERATION_OVERSPECIFICATION.md:10-20) — and the
  rarer `ld→other→xm` OTB precursor is **absent though legal** (OTB_GENERATION_GAP.md:16-25,57-60);
- flipping one padding/register bit counts as a "new" model, so the budget is spent on **padding
  permutations of the same two mechanisms** (2,834 skeletons = 47 cores in costumes;
  ENUMERATION_OVERSPECIFICATION.md:21-23).

Because the true count at `exactly 6` is **orders of magnitude above the cap** (§3), the cap is
always hit **long before** exhaustion — the enumerator never gets anywhere near the UNSAT frontier.

---

## 3. Is the space finite / canonical / exhaustible at `exactly 6`?

### 3.1 Finite — yes
The run scope is `for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool`
(STT_6.als:317, SPT_6_oneLP.als:329). Every sig is bounded (6 Instruction; the Operand subsigs and
State ≤ 9; the three booleans = 1), so the set of instances is a **fixed finite bound**. UNSAT is
well-defined and, in principle, reachable.

### 3.2 Canonical — yes (so UNSAT would be *meaningful*, not permutation-spinning)
Reaching UNSAT only means something over **canonical** instances; otherwise you block atom
relabelings forever. The model already secures this:
- **idx symmetry-breaking:** `idx` bijects the 6 Instruction atoms to fixed position atoms
  `IX0..IX5` with a static order, and `idx_matches_spo` ties that order to program order
  (STT_6.als:280-295) — collapsing the 6! instruction-atom permutations to one.
- **boolean atoms pinned:** `exactly 1 rBool/cBool/tBool` (:317) removes boolean-token permutations
  (the memory note records this was ~98% of the old duplication).
- **Kodkod lex-leader SBP** (`opt.symmetry=80`) breaks the residual State/Operand atom symmetry.

**Empirically verified this session at `exactly 3`:** the raw `sol.next()` count (80) **equals** the
`find_duplicates.py` canonical count — `80 unique instance(s), 0 file(s) in duplicate groups`
(canonicalization: find_duplicates.py:24-75, fingerprints kind/resolved/committed + canonicalized
slot states + canonical `(pc,slot)` rf/ddi edges). So the enumeration is *already* canonical-unique;
there is **no duplicate-driven blowup** to fix before reaching UNSAT. (Verified at N=3; the
symmetry-breaking is identical in form at N=6, so this is expected to hold there too — worth a
one-line re-confirm when a staged run produces N=4 XML.)

### 3.3 Exhaustible at `exactly 6` — effectively NO
Measured counts from throwaway scope-reduced copies (`reduce_scope.py` rewrote the IX sigs/facts +
run scope for `exactly N`; counted with `a6CountProgress`, same `opt.symmetry=80` as production;
UNSAT = genuinely exhausted, TIMEOUT = still SAT at the budget, so the count is a **floor**):

| scope `exactly N` | STT_6                         | SPT_6_oneLP                   |
|-------------------|-------------------------------|-------------------------------|
| N = 2             | **UNSAT at 0** (0.4 s)        | **UNSAT at 0** (2.9 s)        |
| N = 3             | **UNSAT at 80** (2.3 s)       | **UNSAT at 194** (15.5 s)     |
| N = 4             | ≥ **6,748**, no UNSAT in 45 s | ≥ **1,454**, no UNSAT in 30 s |
| N = 5             | ≥ **7,101**, no UNSAT in 60 s | (not run)                     |
| N = 6 (**production**) | ≥ **6,372**, no UNSAT in 60 s; **production cap 100k is hit** | production cap 100k/5k hit |

Reading the table:
- **N=2 is UNSAT at 0:** a speculative leak needs ≥3 instructions (branch + two loads), so the two
  smallest scopes bracket the floor precisely.
- **The count explodes with N:** STT jumps from 80 (N=3, fully exhausted) to **>6,748** at N=4
  (≥ 84× and *not finished*), and the true N=6 count exceeds the 100k cap (every doc). Extrapolating
  the per-instruction multiplicative growth (each added instruction multiplies kind × resolved ×
  committed × operand × rf-edge choices), `exactly 6` is plausibly in the **10^6–10^8+** range.
- **The enumeration rate *decays*** as it runs: `sol.next()` accumulates one blocking clause per
  model, so the CNF grows (observed: clause count ticking `…115146, 115147, 115148…`) and each
  successive solve is slower. STT managed only ~100–150 inst/s and *falling* (N=4: 6,748/45 s;
  N=6: 6,372/60 s). SPT is heavier still (its defense predicate yields a bigger CNF; N=4 ≈ 48 inst/s,
  first solve 4.2 s). So even 10^6 instances would be **hours-to-days of pure solver time**, and
  10^7+ is out of reach entirely.

**Therefore:** `exactly 6` is finite and canonical but **not practically exhaustible** by flat
enumeration. "Reach UNSAT at the current bound by removing the cap" is infeasible — which is exactly
why the fix has to change *what we exhaust*, not just *how far we count* (§5).

---

## 4. How to actually reach UNSAT — the enumeration strategy

The principle: **block accepted (canonical) results persistently so the solver is forced to genuinely
exhaust and finally returns UNSAT** — but choose a **granularity** whose canonical space is small
enough to finish, and use **incremental solving** so blocking stays cheap.

### 4.1 Blocking-clause enumeration (the mechanism)
After each accepted instance, add the **negation of its canonical signature** as a persistent fact,
not just a one-model block. When the conjunction of the model + all negations is UNSAT, the space is
provably exhausted. This is already implemented at the skeleton granularity in
`a6DiverseModels.java` (build block :67-107; loop + UNSAT report :129-140). It is sound under the
model's `idx` symmetry-breaking because the blocks are **position-independent** (existential over
`Instruction`, all references by named one-sigs; :16-19) — they forbid a *mechanism anywhere*, not a
specific atom labeling.

### 4.2 Granularity = what "UNSAT" means (pick deliberately)
- **Full canonical instance** → UNSAT = exhaust *everything*. Tractable only at `N ≤ 3` (§3.3);
  intractable at 6. This is the `sol.next()` space (already canonical per §3.2).
- **Leak-core skeleton** (instructions backward-reachable from the transmitter via `rf`;
  a6DiverseModels) → UNSAT = *no new leak mechanism*. The canonical space here is **tens of cores**,
  so UNSAT is genuinely reachable — this is the research-meaningful "complete."
- **Leak-core × control structure** (add which/how-many branches are unresolved + the commit
  boundary to the block; ENUMERATION_OVERSPECIFICATION.md:168-172, the "second axis") → UNSAT = *no
  new (mechanism × speculation-structure) class*. Larger than core-only but still vastly smaller than
  full-instance; this is the axis that surfaces the multi-branch / OTB / getOldestTaint family.

### 4.3 Dedup is a prerequisite — and it's already satisfied
"Reach UNSAT over canonical instances" requires canonicalization first. Per §3.2 the model's SB +
Kodkod SBP already deliver canonical-unique instances (N=3: raw == `find_duplicates`), so **no extra
dedup pass is needed before blocking** at the full-instance level. For the coarser granularities the
block itself *is* the canonical quotient (skeleton / skeleton×control), computed structurally in
`skeletonBlock`.

### 4.4 Performance: incremental Kodkod (the actual blocker to reaching UNSAT)
Both the naive `sol.next()` loop (my probe) and `a6DiverseModels` (re-translate per step,
:130-131) slow down as blocks accumulate; that decay — not a small true count — is why
`a6DiverseModels` stalls at ~6 (ENUMERATION_OVERSPECIFICATION.md:159-160). The fix is **incremental
solving**: add the blocking clause to the *live* Kodkod solver instead of re-parsing/re-translating
the whole model each step (ENUMERATION_OVERSPECIFICATION.md:180-183, step 1), or **batched blocking**
(block a class per solve). This is the single highest-leverage engineering change for making UNSAT
actually reachable in wall-clock time over the core / core×control spaces.

This whole item is **B1** in `ALLOY_MODEL_CHANGES.md:109-112` ("diversity-driven enumeration … lives
in the driver … not a `.als` edit, so no model approval needed").

---

## 5. "Clean up the act" — the recommended principled scheme

**Replace the arbitrary 100k cutoff with completeness claimed over spaces we can actually exhaust.**
Do **not** try to exhaust full `exactly 6` (intractable, §3.3). Instead, a **hybrid (a)+(b)+(c)**:

**(a) Staged exact bounds — a hard completeness guarantee at small sizes.**
Enumerate to **real UNSAT** at `exactly N` for `N = 2,3,4,…`, stepping up until the solver no longer
finishes in budget. Reaching UNSAT at each N = *provably every canonical STT/SPT leak of that
instruction count*. My probe shows `N ≤ 3` finishes in seconds and `N = 4` in minutes-plus; record
and publish the **largest fully-exhausted bound** (likely N=4, maybe N=5 with incremental solving).
Defensible statement: "for programs up to K instructions, we have **every** canonical leak."
(This is the staged idea in `STAGED_ENUMERATION.md`; the per-N IX scaffolding can be generated
mechanically, as my throwaway `reduce_scope.py` does.)

**(b) Blocking-clause-to-UNSAT over the leak-core (and core×control) quotient at `exactly 6` — full
coverage of leak *mechanisms*.**
Run `a6DiverseModels` (made incremental, §4.4) at `exactly 6` to **true UNSAT over the core space** —
which *is* reachable because that space is small — yielding **every distinct leak mechanism at 6
instructions** (the OTB / multi-hop shapes the flat 100k produced ~0% of;
ENUMERATION_OVERSPECIFICATION.md:133-138), not 100k permutations of two. Add the control axis to the
block (§4.2) to also exhaust the speculation-structure classes.

**(c) Flesh out each exhausted core with a *capped* number of concrete tests.**
A per-core cap is legitimate here: you are capping **padding variety around a core you have already
proven complete over**, not capping the space you claim completeness on. This is the Stage-2
flesh-out in `STAGED_ENUMERATION.md` (seed each core, enumerate ≤ `--per-core` concrete 6-instruction
programs). gem5 then runs this smaller, complete-by-construction corpus.

**Net completeness statement (the honest "done"):** complete over the **canonical leak-mechanism
space** (UNSAT via core/core×control blocking) **and** the **small-N full space** (UNSAT via staged
bounds) — *not* over the intractable full `exactly-6` space. That is the principled replacement for
the 100k cutoff.

### 5.1 Driver changes (Java — NOT owner-gated)
- **Incremental / batched blocking in `a6DiverseModels.java`** so it reaches UNSAT over the core
  space in reasonable time, and **add the control axis** to the block (§4.2, §4.4).
- **Emit an explicit `reached_unsat: true/false`** (+ count, scope, elapsed) into the xml-corpus
  meta from the enumerator, so "complete vs capped" is authoritative instead of the current
  count-vs-cap heuristic (DASHBOARD_PLAN.md:100-104, :156). Trivial add to `a6CountModels` /
  `a6CountProgress`.
- **A staged-bounds orchestrator** (sibling of `stage_pipeline.py`) that loops `N=2,3,4,…` to UNSAT,
  records the largest exhausted bound, and writes the corpus. *Caveat:* scope reduction rewrites the
  hardcoded `IX0..IX5` block (model text). Done as a **driver-generated throwaway scope** it is
  tooling; **committed as a model variant it is owner-gated.** Flag for Anna which form she wants.

### 5.2 Model / scope changes (OWNER-GATED `.als`)
- **Variable / stepped length (B4).** `exactly 6` is baked into `IX0..IX5` + `idx_surjective` +
  `lt_ix` (STT_6.als:38-43,280-295), so stepping N is **real model surgery** (add/parameterize IX
  sigs + facts), not a scope bump (ENUMERATION_OVERSPECIFICATION.md:174-178; claudelog.md:357).
- **Joint minimality (B2)** — *handled by the companion agent*; relaxing per-branch minimality
  enlarges the legal space but **needs B1 to surface the shapes** (ALLOY_MODEL_CHANGES.md:113-118).
- **Instruction-minimality / core-vs-padding split (B3)** to stop padding waste
  (ALLOY_MODEL_CHANGES.md:119-121).
- **New core models** (`STT_6_core.als`, an `SPT_6_oneLP_core.als`) are new `.als` files → owner
  eyeball (STAGED_ENUMERATION.md:81-83).

### 5.3 Rerun implication for STT_6 and SPT_6_oneLP
Switching from "flat cap via `a6CountModels`" to "staged-UNSAT + core-blocking-to-UNSAT" is a
**Stage-1 change** → both testsets must be **regenerated from `xml` onward (`--force`)** and every
build **re-swept** (ALLOY_MODEL_CHANGES.md:22-25 + rerun matrix :141-153). The new corpus will be
**smaller but complete-by-construction** (every core + bounded flesh-out) instead of 100k-of-2-shapes.
**Batch this with the pending A1/A2 (protset/rf) and B2/B3 model edits** so the regen is paid **once**
(ALLOY_MODEL_CHANGES.md:149-153), not per change. Order: land driver (B1 incremental) + any approved
`.als` edits together → `pipeline.py xml --force` → re-sweep via `testrun.py` → re-triage.

---

## 6. Reproduce the measurements

Throwaway artifacts in the session scratchpad (`…/scratchpad/unsat_probe/`; nothing in the repo
touched):
- `a6CountProgress.java` — enumerates via `sol.next()` to UNSAT or a wall-clock budget, printing the
  count (so a budget still yields data); `opt.symmetry = 80` to match production.
- `reduce_scope.py` — reads a canonical `.als`, writes `*_N{2..6}.als` copies with the IX
  symmetry-breaking sigs/facts + run scope rewritten for `exactly N` (N=6 is byte-identical to the
  source — verified).
- Commands: `javac -cp alloy6.jar -d <sp> a6CountProgress.java`; then
  `java -cp alloy6.jar:<sp> a6CountProgress <sp>/stt/STT_6_N{N}.als 5000000 <budget_ms>`.
  Canonical check: `java … a6CountModels STT_6_N3.als <out> 1000` then
  `python3 -I STAGE2_compilation/find_duplicates.py <out>` → `80 unique, 0 duplicate`.

**What needs the container (cannot run here):** a *full* staged run to the largest-exhaustible bound
and an incremental-Kodkod `a6DiverseModels` run to UNSAT over the core space at `exactly 6` — those
want real compute/time and the gem5 re-sweep, which this local box cannot reach.
