# Why SimSpect's 100k tests find fewer bugs than AMuLeT's few hundred — the enumeration over-specifies

**For:** Anna · **Date:** 2026-06-09 · session `5:invisispec`
**Claim:** Our enumeration is **simultaneously over-constrained on the leak dataflow and under-constrained on
padding**. The result: 100,000 STT_6 tests collapse to **~2 effective leak shapes** (47 leak-cores total,
98% a single `load→transmitter` shape), single-source, depth-1 — strictly *less* leak-mechanism diversity
than a random generator. This is measured, not theorized (scripts: `/tmp/diversity.py`, `/tmp/xmitfeed.py`,
`/tmp/leakcore.py`; rerun on `testsets/STT_6/xml/`).

## The measurements (STT_6, 100k instances, sampled 6–8k)
| metric | value | meaning |
|---|---|---|
| distinct kind-sequences (6 opcodes in order) | 298 | looks diverse… |
| distinct full skeletons (+rf edges) | 2,834 | …still looks diverse… |
| **distinct LEAK-CORES (padding projected out)** | **47** | the real number |
| leak-core = 2 instructions (`src → xmit`) | **98.0%** | the leak is one hop |
| transmitter in-degree = 1 (single rf feeder) | **99.6%** | no multi-source merges |
| transmitter fed directly by a single TLoad | 99.6% | one shape |
| dataflow chain depth = 1 | 98.4% | no deep chains |
| top 6 leak-cores (each ~16%) | all `load→load` / `load→branchx` | ≈2 shapes wearing costumes |

So the 2,834 "skeletons" are **2 leak mechanisms permuted across leak-irrelevant padding** (where the
`Othern`/`Otherx`/`Branchn` fillers sit). We pay for diversity in the dimension that doesn't matter.

## Is it test length? — No (mostly)
`run gen_lit ... for 9 but exactly 6 Instruction` fixes length, which *caps* the leak-core at ~4 and blocks
variable-length exploration. But length is **not** the dominant cause: even within 6 instructions a depth-2/3
core fits, yet **98% are depth-1**. The enumeration never *reaches* the deeper region it's allowed to use.
The dominant causes are the minimality predicate and the SAT enumeration order (below).

## Root causes, ranked

### 1. Minimality over-constrains the DATAFLOW → forbids multi-source leaks (the OTB class)
`gen_useful_litmus` (STT_6.als:301–311):
```
all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]   // each branch individually necessary
all s: State                            | secure_speculation_scheme_p[RS->s]   // each state individually necessary
```
This demands that **every** unresolved branch be *individually* necessary: resolving it alone must make the
program secure. A **two-source merge** (transmitter fed by two tainted loads under two branches — exactly
recon getOldestTaint / OTB, and the multi-resource shapes UV2/UV5 want) **fails** this: resolving one
branch still leaks via the other → "not minimal" → pruned. So the model **structurally cannot emit**
in-degree≥2 leaks. This is the measured `99.6% in-degree 1`. Minimality is a *soundness/canonicalization*
nicety that is silently amputating the most interesting bug class.

### 2. Simplest-first SAT enumeration + symmetry-breaking → collapses to the trivial witness
The solver emits structurally-smallest models first; with a 100k cap it never advances past the trivial
`load→transmitter` core (measured: 98% depth-1, 47 cores). This is the `gen_lit`-fills-the-cap-with-simple-
shapes effect already noted in `OTB_GENERATION_GAP.md`. Enumeration *order*, not just the predicate, starves
the rare shapes.

### 3. Paradoxical UNDER-constraint on instructions (no RI-minimality) → wastes the budget on padding
`gen_useful_litmus` prunes redundant **states** (RS) and redundant **resolvedness** (RR) but **not redundant
instructions** (there is no `RI`-minimality clause). So the model freely adds leak-irrelevant
`Othern`/`Otherx`/`Branchn` fillers, and the 100k slots fill with **padding permutations** of the same 2
cores. That is the 298 kind-sequences / 2,834 skeletons / 47 cores gap.

### 4. Fixed length (`exactly 6 Instruction`) → caps core size, no variable-length sweep
Hard-bounds chain depth to ~4 and prevents the variable-length exploration AMuLeT does. Minor next to 1–3,
but real, and it interacts badly with (3): more length just buys more padding unless (1)/(2) are fixed.

## The paradox in one line
**Over-constrained where it hurts (minimality kills multi-source dataflow), under-constrained where it
wastes (no instruction-minimality → padding noise).** Net per-test bug-yield is far below random: AMuLeT's
random gadgets have high entropy *in the leak dimension*; ours have ~zero entropy there (all mass on 2
shapes) and spend their entropy on padding. That is the "actively worse than randomness."

## What to change (ranked by leverage) — ALL owner-gated (`.als` edits)
1. **Stratified / blocking-clause enumeration (highest leverage, no semantics change).** Stop taking the
   solver's simplest-first 100k. Enumerate by **leak-core skeleton**: after K instances of a given core, add
   a blocking clause forbidding that core, forcing the solver into a new region. Converts 100k-of-2-shapes
   into 100k-across-all-reachable-cores. (bugsynth "skeleton-stratified enumeration".)
2. **Relax minimality to admit multi-source leaks.** Replace the per-branch "each individually necessary"
   with a *joint* notion: insecure under `no_p` AND not reducible by removing a *single non-source* element,
   but **allow ≥2 jointly-necessary tainted sources**. Unlocks OTB/getOldestTaint without `otb_class`
   forcing. (This is the general version of the bugsynth `otb_class` hack.)
3. **Add instruction-minimality OR separate padding from core.** Either add an `RI`-minimality clause to kill
   leak-irrelevant fillers, or enumerate leak-cores first and treat padding as a separate capped dimension —
   so the budget isn't burned permuting noise. Pair with (1).
4. **Variable / longer length.** Sweep instruction count over a range instead of `exactly 6`, and raise the
   bound, so deeper chains/bigger gadgets appear. Only useful *after* (1)/(2)/(3) (else it adds padding).
5. **Extend the transmitter/edge vocabulary to cover the structurally-absent bug classes** (so they're
   *rediscovered*, not forced): store-address transmitter (→KV3), control-dependence `cdep` edge (→implicit
   flow), split/misaligned concretization flag (→UV4), fetch-path transmitter (→KV1). Each is its own
   owner-gated extension.

**Recommended first move:** validate (1)+(2) cheaply — run a *copy* of the model with the per-branch
minimality clause relaxed and a blocking clause on the `load→load` core, then re-measure leak-core count.
If the distinct-leak-core number jumps from 47 toward the hundreds (and OTB-shaped in-degree-2 cores appear),
that confirms the diagnosis and the fix direction before any canonical-model edit.

## Validation experiment (2026-06-09) — model copy `STT_6_multisource.als`

Built `STAGE1_alloy/models/STT_6_multisource.als` (copy of STT_6.als; ONLY `gen_useful_litmus` changed:
per-branch `all i: unresolved | secure[RR->i]` → aggregate `secure[RR->unresolved]`). Findings:

1. **Compiles + generates** (400 instances via `a6CountModels`). ✔
2. **Relaxation alone does NOT change what enumeration SHOWS:** first 400 instances are still 100%
   single-source / depth-1 (8 leak-cores). This is the proof that **#2 needs #1** — relaxing minimality
   *enlarges the legal space* but `sol.next()` still returns the structurally-smallest models first, so we
   never *see* the new shapes without diversity-driven enumeration. (Matches Anna's point: the diversity/
   second-source belongs in the enumeration phase, not the predicate.)
3. **Discriminating SAT probe proves the relaxation unlocked a real new class.** Probe = "a leak where SOME
   unresolved branch is NOT individually-securing" (`some i: unresolved | not secure[RR->i]`):
   - **base STT_6 → UNSAT by construction** (base contains `all i: secure[RR->i]`; direct contradiction).
   - **STT_6_multisource → SAT** (3 models found fast).
   So the relaxed model admits leaks with **multiple jointly-necessary unresolved branches** that base
   minimality structurally rejects — the class that includes getOldestTaint-with-two-branches and
   pending-squash-style control-multiplicity.
4. **Nuance on the OTB *dataflow* merge:** forcing the ALU-merge shape (`other` merging 2 loads → xmit) is
   **SAT in BOTH** base and relaxed — i.e. the 2-load *dataflow* merge was never forbidden by minimality
   (it's the enumeration/cap gap from `OTB_GENERATION_GAP.md`). What minimality actually forbade is
   **control-multiplicity** (≥2 jointly-necessary unresolved branches). So: **#2 unlocks the multi-branch /
   jointly-necessary-speculation class; #1 (enumeration diversity) is what surfaces the rare dataflow
   merges.** Both are needed; they unlock different things.

## Diversity driver (2026-06-09) — `STAGE1_alloy/a6DiverseModels.java` (BUILT + WORKS)

Fix #1 lives in the driver. `a6CountModels.java` uses Kodkod `sol.next()`, which blocks only the EXACT
previous model (flip one padding bit → "new" model). `a6DiverseModels.java` instead, after each accepted
solution, appends a top-level `fact { not (<leak-core shape>) }` and re-solves, where the leak-core =
the instructions backward-reachable from the transmitter via rf. The block is **position-independent**
(an existential over `Instruction`, all references by named one-sigs), so it forbids that leak *mechanism*
appearing anywhere — not just at the same positions. ⇒ one representative per leak-core shape.

Two iterations to get it right (kept as a lesson):
- v1 blocked the full 6-position **skeleton** (kind+resolve+xm+rf by position) → 120 distinct skeletons but
  still only **8 leak-cores** (it enumerated 120 padding costumes of the same cores). Wrong signature.
- v2 blocks the **leak-core** position-independently. Bug: `(a.outreg -> b.inreg) in rf` is a *subset*
  test that silently fails when a branchx has 2 inreg operands (only one fed) → block never fired. Fixed to
  the *some-edge-exists* form `some (a.outreg <: rf :> b.inreg)`. After the fix:

**Result (STT_6_multisource.als + leak-core diversity driver):** 6 models → **6 distinct leak-cores
(100% unique)**, and **66% are depth-2 multi-hop chains**, including `TLoad → TOtherx → TLoad`-xmit and
`TBranchx ← TOtherx ← TLoad` — i.e. an **ALU `other` op on the dataflow path between the load and the
transmitter = the OTB / getOldestTaint precursor**, which the base 100k enumeration produced ~0% of in the
common case. So `multisource model + leak-core blocking` immediately surfaces deeper, multi-hop, OTB-shaped
mechanisms. **This is the demonstrated fix.**

**Limitation (honest):** the driver re-parses + re-translates the whole model each step, and each *new*
distinct leak-core gets harder to find as existential blocks accumulate + the relaxed space is larger — so
it's slow (seconds/step early, growing; a 50-core run stalled past ~6 within the time budget). Fine for
sampling tens–hundreds of distinct cores; for 100k-scale it needs **incremental Kodkod** (add the blocking
clause to the live solver instead of re-translating) or **batched blocking** (block a class of skeletons per
solve). That optimization is the next engineering step; the diversity *mechanism* is proven.

**Usage:** `java -cp alloy6.jar:. a6DiverseModels <model.als> <out_dir> [limit]` (compile with
`javac -encoding UTF-8 -cp alloy6.jar:. a6DiverseModels.java`).

## Is the stall "only ~6 cores"? — measured: NO, it's a perf wall + two diversity axes (2026-06-10)

Anna asked whether the driver stalls near 6 simply because there are only ~6 leak-cores. Measured:
- **Baseline 45,000 STT_6 instances → exactly 10 distinct *structural* dataflow cores** (kinds+rf edges, no
  resolve/commit bits), **98% on the 2 trivial 2-instr shapes**, max enumerated core size = 3 instr, **zero
  4-instr cores.** So the *enumerated* dataflow diversity is tiny (~10).
- **BUT a 4-instruction depth-3 chain core (`load→other→other→load`-xmit) is SAT at exactly-6-Instruction**
  (forced probe → 2 models instantly). So deeper cores are **legal but never enumerated** — the ~10 is an
  enumeration/cap artifact, **not** a hard scope ceiling. The diversity driver stalling at 6 was therefore a
  **performance wall** (re-translate-per-step cost grows with accumulated blocks), **not** core exhaustion;
  cores beyond the 6 it found provably exist.

This separates **two orthogonal diversity axes**, and the base enumeration collapses BOTH (98% on 2 dataflow
cores × trivial control):
1. **Dataflow-core shape** (what `a6DiverseModels` blocks on). Capped *in practice* by (a) the 6-instruction
   scope keeping cores to ~2–4 instr, and (b) enumeration/driver perf never reaching the legal-but-rare deep
   ones. Lever: faster diversity enumeration (incremental Kodkod) to reach the deep cores; and for cores
   *larger* than ~4 instr, raise the instruction count.
2. **Control / speculation structure** (which & how-many branches unresolved, commit boundary) — the axis the
   minimality relaxation (#2) unlocks (multi-branch jointly-necessary leaks). `a6DiverseModels` does **NOT**
   capture this — it blocks dataflow-core only, so all multi-branch variants of `load→xmit` look like one
   core and get blocked after the first. To enumerate axis 2, the block must include branch/commit/resolve
   structure, not just rf. AMuLeT's random gadgets vary heavily on this axis for free.

**Two notes on instruction count (length).** (a) `exactly 6 Instruction` is **baked into the symmetry-
breaking**: positions `IX0..IX5` + `idx_surjective`/`lt_ix` are hardcoded to 6, so raising length is real
model surgery (add `IX6..`, extend those facts), not a one-line scope bump. (b) Length only lifts the
*dataflow* axis (bigger/deeper cores); it does nothing for the control axis. So "is it length?" — length is
ONE of three real levers (length, diversity-enum perf, control-axis blocking), not the whole story.

**Corrected next steps (ranked):**
1. **Incremental-Kodkod** in `a6DiverseModels` (add the blocking clause to the live solver instead of
   re-translating) → reaches the legal-but-rare deep dataflow cores fast; turns the perf wall into real
   coverage at scope 6 already.
2. **Add the control axis to the diversity block** (branch/commit/resolve structure), so #2's multi-branch
   class is actually enumerated, not collapsed.
3. **Raise instruction count** (model surgery: IX6.. + idx facts) to lift the dataflow-core size ceiling
   above ~4 — needed for the biggest gadgets, owner-gated.

## Cross-refs
`mdsToRead/OTB_GENERATION_GAP.md` (the OTB-specific instance of this), STATUS.md bugsynth "DIVERSITY" TODO,
`bugsynth/FINDINGS_SUMMARY.md`. Measurement scripts in `/tmp/{diversity,xmitfeed,leakcore}.py`.
