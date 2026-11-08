# Two-phase (Stage 1 core → Stage 1.5 flesh-out) Alloy models — drafts for review

> **⛔ UNAPPROVED DRAFTS.** `STAGE1_alloy/models/proposed_twophase/SPT_6_oneLP_core.als` and `Recon_6_core.als` are new, unreviewed `.als` files. They, and anything enumerated from them (`testsets/*__twophase_draft/`), must **not** feed any production testset, campaign or paper number until Anna signs off clause by clause. No existing `.als` was modified (sha256 of `STT_6.als`, `SPT_6_oneLP.als`, `Recon_6.als`, `STT_6_core.als`, `STT_6_stl.als` re-checked unchanged after the runs started).

Written 2026-11-03 by the two-phase-models session (Anna's ask: "make sure we have two phase models for each alloy model we have, and they are up to date with all of our design decisions and grounded in the spec", then "start alloy runs of the finished models' first stages"). Scope was cut mid-task by the coordinator to the three production models (STT_6, SPT_6_oneLP, Recon_6); variants are inventoried but not drafted.

## TL;DR

- **STT_6** already has a two-phase version: `STAGE1_alloy/models/STT_6_core.als` (Stage 1) + `STT_6.als` itself (Stage 1.5, via `stage_seed.py` / `stage_pipeline.py`). It is **not stale**: re-deriving it from today's `STT_6.als` with the same three changes gives a file identical to `STT_6_core.als` once comments and whitespace are ignored. Only its comment is wrong ("same idx/IX symmetry-breaking as STT_6.als", `STT_6_core.als:285-286`; idx was removed) and its doc path is old (`mdsToRead/` → `wiki/findings/mdsToRead/`). Not edited.
- **SPT_6_oneLP** and **Recon_6** had none. Drafted `SPT_6_oneLP_core.als` and `Recon_6_core.als` with `proposed_twophase/derive_core.py`, which applies exactly the prototype's three changes and refuses if any anchor isn't found exactly once. Defense blocks and every other line are byte-identical to the production models.
- Tiny-scope checks: STT_6_core and Recon_6_core load and are SAT at `but 3` (the same 2 cores each: the Spectre-v1 skeleton with a load or a `br_x` transmitter). **SPT_6_oneLP_core loads but no core was found**: UNSAT at `but 3` (exhausted in 72 s) and 0 instances in 7–9 min at `but 4` / `but 5`, while SPT's own RR+RC+RS semantics on the same skeleton give 200 instances in 31 s at `but 4`. Its satisfiability is open; the Stage-1 run below is the test.
- **Stage-1 runs started** (background, at most 3 at once, cap 100000, 6 h timeout, disk guard) for STT_6, Recon_6 and SPT_6_oneLP. See "Runs".
- The big open call is still **RO+RI vs RI-only** in Stage 1 (URGENT_TODO #2, BIGFIG_FACT_AUDIT D4). The drafts follow the prototype (RO+RI), which is what the paper text says; new evidence below.

## Inventory

Status from `specs/alloy_relaxations.json` (`enumerated_final`), `specs/alloy_models.json`, `STAGE1_alloy/models/MANIFEST.md`; builds from `specs/defense_units.json`.

| Defense | Production file | Status | gem5 build(s) run against | Two-phase version? | Notes |
|---|---|---|---|---|---|
| STT | `STT_6.als` (sha256 `7a6ac4c0…`) | production, enumerated_final | `/work/stt` (STT-Spectre); `gem5-recon-modded` scheme 2 (Recon-STT), schemes 1/3 (Delay, DoM); `gem5-spt` STT-like subimpl; amulet SpecLFB / InvisiSpec / CleanupSpec reuse STT_6 | **yes, existing** `STT_6_core.als` (`d1fd8a64…`), up to date | Stage-1 run started (existing file, read only) |
| SPT | `SPT_6_oneLP.als` (`713d0904…`) | production, enumerated_final | `gem5-spt` (SpectreSafeFence + Futuristic / InvisibleSpec / disableUntaint variants) | **draft** `proposed_twophase/SPT_6_oneLP_core.als` (`63611dc1…`) | no core found at tiny scope yet; Stage-1 run started |
| Recon | `Recon_6.als` (`01252c82…`) | production, enumerated_final | `gem5-recon-modded` | **draft** `proposed_twophase/Recon_6_core.als` (`dfb81a80…`) | reveal clause is a no-op (R-1), so its cores equal STT_6's; Stage-1 run started |
| STT (STL) | `STT_6_stl.als` | variant, Anna-approved as a new file | `/work/gem5-recon-stl` | no (out of reduced scope) | RO+RI core is UNSAT by construction (see D4 evidence); RI-only is SAT (129 raw at `but 3`) |
| STT | `STT_6_commitsplit.als` | variant, clause review pending (URGENT_TODO) | `/work/stt` candidate testset | no | replaces clauses (b)/(c); needs its own core once reviewed |
| STT | `STT_6_futuristic.als` | variant, unreviewed | `/work/stt --threatModel=Futuristic` (planned) | no | |
| STT (OTB) | `STT_6_multisource.als` | variant, never enumerated | `gem5-recon-modded` (`recon_otb` unit) | no | OTB now lives in Stage 2 interleave (decision 2026-10-30), so a core is not needed for OTB |
| SPT | `SPT_6.als` (= `SPT_6_full.als`), `SPT_6_oneLP_noSTLF.als` | variants | `gem5-spt` | no | |

## How the two-phase models are built (and the decisions they encode)

**Stage 1 = `<X>_core.als`**, a copy of `<X>.als` with exactly the three changes of the prototype (`diff -u STT_6.als STT_6_core.als`; `wiki/findings/mdsToRead/STAGED_ENUMERATION.md:28-38`): (1) idx/IX0..IX5 symmetry-breaking removed so a core is not pinned to 6 positions; spo program-order facts kept; (2) operand-minimality (e) `all o: Operand | secure_speculation_scheme_p[RO->o]` and instruction-minimality (f) `all i: Instruction | secure_speculation_scheme_p[RI->i]` added to `gen_useful_litmus`, on top of the model's own RR + RC + RS (and, for SPT, its exactly-one-leak-point clause, kept verbatim); (3) scope `exactly 6 Instruction` → `but 6`. **Stage 1.5 = `<X>.als` itself** plus the structural `seed_core` predicate from `stage_seed.py`, spliced in by `stage_pipeline.py:58-65`; the needle it needs (`run gen_lit {\n  gen_useful_litmus\n}`) is present exactly once in all three production models (checked), so no Stage-1.5 model file is needed.

Decisions encoded, with where they come from:

- Stage 1 enforces every relaxation (RI, RO, RS, RC, RR); the first interleaving round turns RI and RO off but keeps state-sharing: paper `sections/pipeline.tex:28-52` ("we enforce that our graph is minimal along certain dimensions", the five relaxations) and `:58` ("we define a first round of instruction interleaving, which we do in the Alloy by removing some of the relaxations … we still require all instructions to share state that is necessary to the leakage backbone"; the commented line under it names RI and RO). Stage 1.5 keeping RS + `no_extra_inst` is that state-sharing rule.
- Figure `tikz/pipeline_full_8pt1col.tex` Stage 1.5 slabs: "+4. Pin: graph contains target Stage-1 graph", "1. Same as Stage 1", "2′. Loosened minimality", "3. Same as Stage 1": the seed + unchanged skeleton + unchanged defense block.
- Stage 1.5 becomes a real pipeline stage (Anna, 2026-11-02, `URGENT_TODO.md:32-33`): the drafts are written so `stage_pipeline.py --core-model proposed_twophase/<X>_core.als --flesh-model <X>.als` works unchanged. Wiring it into `pipeline.py` is not done.
- OTB is manufactured in Stage 2 interleave, not in the baseline (Anna, 2026-10-30, `URGENT_TODO.md:81-83`): the cores stay single-source; nothing added for OTB.
- The defense lives in the three-clause defense block; everything else is copied (CLAUDE.md): `derive_core.py` touches only the idx block, `gen_useful_litmus` and the `run` scope. Model-specific source facts (SPT's `one_insecure_speculation_scheme_p`, Recon's `p`-parameterized `hardware_protection_policy`) are copied as they are.
- Not encoded because still undecided: RO+RI vs RI-only (D4), `rf_from_most_recent_writer` alignment, the commit split, the resolution-flag-only-on-branches/stores question, and every defense-block paper fix below.

## Exact diffs against the production models

### STT_6.als → STT_6_core.als (existing prototype, unchanged)

Hunks: idx/IX removal (change 1), RO/RI clauses plus relabelled comments (change 2), scope (change 3). The comment block at the top of `gen_useful_litmus` is the stale one.

```diff
--- STT_6.als	2026-10-13 15:32:00
+++ STT_6_core.als	2026-10-20 17:10:14
@@ -34,18 +34,12 @@
 one sig TOthern  extends InstrType {} // ALU/reg->reg, doesnt xmit
 one sig TOtherx  extends InstrType {} // ALU/reg->reg, xmits
 
-// fixed position atoms for symmetry-breaking index (one sig = no atom permutation)
-one sig IX0 {} -- spo position 0 (first)å
-one sig IX1 {} -- spo position 1
-one sig IX2 {} -- spo position 2
-one sig IX3 {} -- spo position 2
-one sig IX4 {} -- spo position 2
-one sig IX5 {} -- spo position 2
+// [STAGE-1 CORE] idx/IX symmetry-breaking REMOVED (ordering rules stripped per
+// staged-enum design) so cores are not pinned to a fixed length/positions.
 
 // single concrete instruction sig
 sig Instruction {
 	kind: one InstrType,
-	idx: one (IX0 + IX1 + IX2 + IX3 + IX4 + IX5),  -- bijection to fixed position atoms
 
 	spo: lone Instruction,
 
@@ -273,48 +267,49 @@
 }
 
 /*********************************************************************************
- * Symmetry breaking — works because Instruction is now a concrete sig
+ * [STAGE-1 CORE] Symmetry breaking (idx/IX ordering rules) REMOVED.
+ * spo program-order facts (spo_acyclic/spo_prior/spo_total) are kept — they are
+ * execution semantics, not symmetry-breaking. a6CountModels runs symmetry=80.
  */
 
--- idx bijection: each instruction gets a unique fixed position atom
-fact idx_bijective { all disj a, b: Instruction | a.idx != b.idx }
-fact idx_surjective { (IX0 + IX1 + IX2 + IX3 + IX4 + IX5) = Instruction.idx }
 
--- IX0 < IX1 < IX2 is a fixed static ordering (no atom permutations possible)
-pred lt_ix[a, b: univ] { (a=IX0 and b in IX1+IX2+IX3+IX4+IX5) 
-				or (a=IX1 and b in IX2+IX3+IX4+IX5)
-				or (a=IX2 and b in IX3+IX4+IX5)
-				or (a=IX3 and b in IX4+IX5)
-				or (a=IX4 and b=IX5)
-
-}
-
--- idx rank mirrors spo rank: position 0 = first in spo, 1 = second, 2 = third
-fact idx_matches_spo {
-	all disj a, b: Instruction | lt_ix[a.idx, b.idx] <=> b in a.^spo
-}
-
-
 /*********************************************************************************
  * Run
  */
-let gen_useful_litmus {
-  not secure_speculation_scheme_p[no_p]
+// ─────────────────────────────────────────────────────────────────────────────
+// STAGE-1 "CORE" VARIANT (copy of STT_6.als; staged-enumeration base).
+// ONLY change vs STT_6.als = gen_useful_litmus turns on EVERY perturbation-
+// minimality clause, so each emitted instance is a MAXIMALLY-MINIMIZED leak core:
+// no removable operand (RO) and no removable instruction (RI) on top of STT_6's
+// existing resolution- (RR), commit- (RC) and state- (RS) minimality. Same sigs,
+// same STT defense, same idx/IX symmetry-breaking as STT_6.als -> instances are
+// re-imposable on STT_6.als with ZERO translation. Stage 2 seeds each core into
+// the real STT_6 (RO/RI OFF) and lets it add extra operands/instructions, capped
+// N per core. See mdsToRead/STAGED_ENUMERATION.md.
+// ─────────────────────────────────────────────────────────────────────────────
+let gen_useful_litmus {
+  not secure_speculation_scheme_p[no_p]                                        // (a) it leaks
 
-  //all i: resolved | secure_speculation_scheme_p[RR->i] or secure_speculation_scheme_p[RC->first_uncommitted]
-  // resolution-min on all unresolved EXCEPT the boundary instr
+  // (b) resolution-min on all unresolved EXCEPT the boundary instr
   all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
-  // boundary instr (first_uncommitted): necessity tested by commit AND resolve together
+  // (c) boundary instr (first_uncommitted): necessity tested by commit AND resolve together
   secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]
-
+  // (d) state-minimality (each State atom individually necessary)
   all s: State | secure_speculation_scheme_p[RS->s]
+
+  // (e) operand-minimality: every operand necessary (no removable operand)
+  all o: Operand     | secure_speculation_scheme_p[RO->o]
+  // (f) instruction-minimality: every instruction necessary (no removable instr)
+  all i: Instruction | secure_speculation_scheme_p[RI->i]
 }
 
 fact no_extra_inst {no ((Instruction-Branchns) - operands.Operand)} //no extra instrs except branches, while interleave fake
 
+// [STAGE-1 CORE] length restriction relaxed: 'exactly 6' -> 'up to 6' Instruction.
+// RI-minimality keeps cores small; this is just the upper bound for the search.
 run gen_lit {
   gen_useful_litmus
-} for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool
+} for 9 but 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool
 
 
 /*********************************************************************************
```

### SPT_6_oneLP.als → proposed_twophase/SPT_6_oneLP_core.als (draft)

Hunk 1: draft header. Hunks 2–3: change 1 (idx/IX sigs, `idx` field, symmetry-breaking facts). Hunk 4: change 2, (e) RO + (f) RI appended after SPT's own RR/RC/RS clauses; the oneLP leak clause `one_insecure_speculation_scheme_p[no_p]` is untouched. Hunk 5: change 3, scope.

```diff
--- SPT_6_oneLP.als	2026-10-13 15:31:59
+++ proposed_twophase/SPT_6_oneLP_core.als	2026-11-03 01:58:51
@@ -1,3 +1,13 @@
+// =============================================================================
+// [STAGE-1 CORE DRAFT — UNAPPROVED, do not use for production testsets]
+// Derived from SPT_6_oneLP.als (sha256 713d0904d91aa9cb5a25a33c1e60ae1156a38caea0d9c1173d4a7959aa898809) by
+// STAGE1_alloy/models/proposed_twophase/derive_core.py --minimality rori.
+// Same three changes as the STT_6_core.als prototype: idx/IX symmetry-breaking
+// removed, minimality (e) RO + (f) RI added to gen_useful_litmus, scope 'exactly 6'
+// -> 'but 6' Instruction. Everything else (skeleton, source facts, defense
+// block) is byte-identical to SPT_6_oneLP.als. Stage 1.5 = SPT_6_oneLP.als itself +
+// stage_seed.py seed (stage_pipeline.py). Review: wiki/design/TWO_PHASE_MODELS.md
+// =============================================================================
 
 
 /*********************************************************************************
@@ -34,18 +44,12 @@
 one sig TOthern  extends InstrType {} // ALU/reg->reg, doesnt xmit
 one sig TOtherx  extends InstrType {} // ALU/reg->reg, xmits
 
-// fixed position atoms for symmetry-breaking index (one sig = no atom permutation)
-one sig IX0 {} -- spo position 0 (first)å
-one sig IX1 {} -- spo position 1
-one sig IX2 {} -- spo position 2
-one sig IX3 {} -- spo position 2
-one sig IX4 {} -- spo position 2
-one sig IX5 {} -- spo position 2
+// [STAGE-1 CORE] idx/IX symmetry-breaking REMOVED (ordering rules stripped per
+// staged-enum design) so cores are not pinned to a fixed length/positions.
 
 // single concrete instruction sig
 sig Instruction {
 	kind: one InstrType,
-	idx: one (IX0 + IX1 + IX2 + IX3 + IX4 + IX5),  -- bijection to fixed position atoms
 
 	spo: lone Instruction,
 
@@ -284,28 +288,12 @@
 }	
 
 /*********************************************************************************
- * Symmetry breaking — works because Instruction is now a concrete sig
+ * [STAGE-1 CORE] Symmetry breaking (idx/IX ordering rules) REMOVED.
+ * spo program-order facts (spo_acyclic/spo_prior/spo_total) are kept — they are
+ * execution semantics, not symmetry-breaking. a6CountModels runs symmetry=80.
  */
 
--- idx bijection: each instruction gets a unique fixed position atom
-fact idx_bijective { all disj a, b: Instruction | a.idx != b.idx }
-fact idx_surjective { (IX0 + IX1 + IX2 + IX3 + IX4 + IX5) = Instruction.idx }
 
--- IX0 < IX1 < IX2 is a fixed static ordering (no atom permutations possible)
-pred lt_ix[a, b: univ] { (a=IX0 and b in IX1+IX2+IX3+IX4+IX5) 
-				or (a=IX1 and b in IX2+IX3+IX4+IX5)
-				or (a=IX2 and b in IX3+IX4+IX5)
-				or (a=IX3 and b in IX4+IX5)
-				or (a=IX4 and b=IX5)
-
-}
-
--- idx rank mirrors spo rank: position 0 = first in spo, 1 = second, 2 = third
-fact idx_matches_spo {
-	all disj a, b: Instruction | lt_ix[a.idx, b.idx] <=> b in a.^spo
-}
-
-
 /*********************************************************************************
  * Run
  */
@@ -320,13 +308,20 @@
   secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]
 
   all s: State | secure_speculation_scheme_p[RS->s]
+
+  // [STAGE-1 CORE] (e) operand-minimality: every operand necessary (no removable operand)
+  all o: Operand     | secure_speculation_scheme_p[RO->o]
+  // [STAGE-1 CORE] (f) instruction-minimality: every instruction necessary (no removable instr)
+  all i: Instruction | secure_speculation_scheme_p[RI->i]
 }
 
 fact no_extra_inst {no ((Instruction-Branchns) - operands.Operand)} //no extra instrs except branches, while interleave fake
 
+// [STAGE-1 CORE] length restriction relaxed: 'exactly 6' -> 'up to 6' Instruction.
+// RI-minimality keeps cores small; this is just the upper bound for the search.
 run gen_lit {
   gen_useful_litmus
-} for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool
+} for 9 but 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool
 
 
 /*********************************************************************************
```

### Recon_6.als → proposed_twophase/Recon_6_core.als (draft)

Same hunks and reasons as SPT. The `p`-parameterized `hardware_protection_policy[p]` defense clause is untouched.

```diff
--- Recon_6.als	2026-10-13 15:31:59
+++ proposed_twophase/Recon_6_core.als	2026-11-03 01:58:51
@@ -1,3 +1,13 @@
+// =============================================================================
+// [STAGE-1 CORE DRAFT — UNAPPROVED, do not use for production testsets]
+// Derived from Recon_6.als (sha256 01252c82c6c0b75522e7c465b92b1c7e9631c94a9bd7a9fa6d7d7b8fc5ab8247) by
+// STAGE1_alloy/models/proposed_twophase/derive_core.py --minimality rori.
+// Same three changes as the STT_6_core.als prototype: idx/IX symmetry-breaking
+// removed, minimality (e) RO + (f) RI added to gen_useful_litmus, scope 'exactly 6'
+// -> 'but 6' Instruction. Everything else (skeleton, source facts, defense
+// block) is byte-identical to Recon_6.als. Stage 1.5 = Recon_6.als itself +
+// stage_seed.py seed (stage_pipeline.py). Review: wiki/design/TWO_PHASE_MODELS.md
+// =============================================================================
 
 
 /*********************************************************************************
@@ -34,18 +44,12 @@
 one sig TOthern  extends InstrType {} // ALU/reg->reg, doesnt xmit
 one sig TOtherx  extends InstrType {} // ALU/reg->reg, xmits
 
-// fixed position atoms for symmetry-breaking index (one sig = no atom permutation)
-one sig IX0 {} -- spo position 0 (first)å
-one sig IX1 {} -- spo position 1
-one sig IX2 {} -- spo position 2
-one sig IX3 {} -- spo position 2
-one sig IX4 {} -- spo position 2
-one sig IX5 {} -- spo position 2
+// [STAGE-1 CORE] idx/IX symmetry-breaking REMOVED (ordering rules stripped per
+// staged-enum design) so cores are not pinned to a fixed length/positions.
 
 // single concrete instruction sig
 sig Instruction {
 	kind: one InstrType,
-	idx: one (IX0 + IX1 + IX2 + IX3 + IX4 + IX5),  -- bijection to fixed position atoms
 
 	spo: lone Instruction,
 
@@ -263,28 +267,12 @@
 }
 
 /*********************************************************************************
- * Symmetry breaking — works because Instruction is now a concrete sig
+ * [STAGE-1 CORE] Symmetry breaking (idx/IX ordering rules) REMOVED.
+ * spo program-order facts (spo_acyclic/spo_prior/spo_total) are kept — they are
+ * execution semantics, not symmetry-breaking. a6CountModels runs symmetry=80.
  */
 
--- idx bijection: each instruction gets a unique fixed position atom
-fact idx_bijective { all disj a, b: Instruction | a.idx != b.idx }
-fact idx_surjective { (IX0 + IX1 + IX2 + IX3 + IX4 + IX5) = Instruction.idx }
 
--- IX0 < IX1 < IX2 is a fixed static ordering (no atom permutations possible)
-pred lt_ix[a, b: univ] { (a=IX0 and b in IX1+IX2+IX3+IX4+IX5) 
-				or (a=IX1 and b in IX2+IX3+IX4+IX5)
-				or (a=IX2 and b in IX3+IX4+IX5)
-				or (a=IX3 and b in IX4+IX5)
-				or (a=IX4 and b=IX5)
-
-}
-
--- idx rank mirrors spo rank: position 0 = first in spo, 1 = second, 2 = third
-fact idx_matches_spo {
-	all disj a, b: Instruction | lt_ix[a.idx, b.idx] <=> b in a.^spo
-}
-
-
 /*********************************************************************************
  * Run
  */
@@ -298,13 +286,20 @@
   secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]
 
   all s: State | secure_speculation_scheme_p[RS->s]
+
+  // [STAGE-1 CORE] (e) operand-minimality: every operand necessary (no removable operand)
+  all o: Operand     | secure_speculation_scheme_p[RO->o]
+  // [STAGE-1 CORE] (f) instruction-minimality: every instruction necessary (no removable instr)
+  all i: Instruction | secure_speculation_scheme_p[RI->i]
 }
 
 fact no_extra_inst {no ((Instruction-Branchns) - operands.Operand)} //no extra instrs except branches, while interleave fake
 
+// [STAGE-1 CORE] length restriction relaxed: 'exactly 6' -> 'up to 6' Instruction.
+// RI-minimality keeps cores small; this is just the upper bound for the search.
 run gen_lit {
   gen_useful_litmus
-} for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool
+} for 9 but 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool
 
 
 /*********************************************************************************
```

## Tiny-scope checks (local, `java -cp alloy6.jar:. a6CountModels`, scratch copies with the scope edited)

| Model | Scope | Result | Time | Exhausted (UNSAT reached)? |
|---|---|---|---|---|
| STT_6_core (RO+RI) | but 3 | 2 cores: `br_n(unresolved) → ld → ld[xm]`, `br_n(unresolved) → ld → br_x[xm]` | 300 s timeout | no (matches the 2026-10-26 finding that the proof is slow without idx) |
| Recon_6_core (RO+RI) | but 3 | the same 2 cores | 15 s | yes |
| SPT_6_oneLP_core (RO+RI) | but 3 / 4 / 5 | 0 / 0 / 0 | 72 s / 420 s timeout / 544 s timeout | yes / no / no |
| STT_6 RI-only (scratch) | but 3 | 129 raw (= the 80 canonical of TWO_STAGE_STT_FEASIBILITY.md §6) | 8 s | yes |
| Recon_6 RI-only (scratch) | but 3 | 129 raw | 24 s | yes |
| SPT_6_oneLP RI-only (scratch) | but 3 / 4 | 0 / 0 | 33 s / 544 s timeout | yes / no |
| SPT_6_oneLP RR+RC+RS on the idx-free skeleton (scratch) | but 4 / 5 | 200 (cap) / 200 (cap) | 31 s / 33 s | capped |
| STT_6_stl RO+RI (scratch, not a repo draft) | but 3 | 0 | 4 s | yes |
| STT_6_stl RI-only (scratch) | but 3 | 129 raw | — | yes |

Peak RSS was 250–400 MB per JVM. In every STT/Recon core only the gate branch is unresolved; no load or ALU op carries an unresolved flag, so the flag-duplicate worry (`URGENT_TODO.md:15`) does not show up in Stage 1 at this scope. Copies and outputs: `results/twophase_stage1_2026-11-03/` (`derived/`, `tiny/`, the `diff_*.txt` files and `tools/`; moved out of the session scratchpad 2026-11-04, the PDF text extracts were not kept).

## Defense blocks vs. the papers (not changed; proposals only)

All three drafts keep the production defense block byte-identical, so they inherit these. The disagreements were found by the 2026-10-28 audits (`wiki/findings/audits/2026-10-28/alloy_STT_6.md`, `alloy_SPT_6_oneLP.md`, `alloy_Recon_6.md`, `APPROVALS.md`). This session re-checked each quote below against the PDFs in `~/Documents/quail/sources/papers/` (PDF page numbers, `pdftotext` per page). Nothing new was found beyond the audits.

**STT (`yu-2019-stt.pdf`).** Matches: speculation contract `uncommitted & has_unresolved_brs_p` = p5 "In the Spectre model, an instruction has reached the visibility point if all older control-flow instructions have resolved"; `leakage_function = Loads.inaddr + Branchxs.inreg` = p5 "Classifying only loads as transmitters will block memory system-related explicit covert channels" plus "classify explicit branch instructions"; stores left out = p5 "We assume that stores trigger a cache coherence invalidation only on retirement, or else are defined as transmitters". Disagreements: (1) untaint is per memory **state**, not per load instance (`STT_6.als:331`), but p6 says "If a load is unsafe, its output is always tainted"; proposed (STT-3, not applied): seed taint from `(Loads & has_unresolved_brs_p[p]).outreg` and test reachability from it. (2) The store-to-load forwarding implicit branch is missing: p5 "identify the implicit branches that represent additional sources of data-dependent resource usage, e.g., store-to-load forwarding", p8 "store-to-load forwarding creates an implicit channel because the load M2 accesses the cache only if it does not alias with the store S"; proposed (STT-1): `fun leakage_function : Operand {Loads.inaddr + Branchxs.inreg + (Stores & (^spo).Loads).inaddr}`.

**SPT (`choudhary-2021-spt.pdf`).** Matches: contract = p3 "in the Spectre model (which covers control-flow speculation), it is when all older control-flow instructions have resolved"; seed of almost all operands = p6 "all program data (memory and architectural registers) starts off as tainted"; declassification = p6 "the operands of transmitters/branches are untainted when the instruction becomes non-speculative"; forward ALU rule = p7 "if all of the instruction's operands are untainted, then its output register becomes untainted". Disagreements: (1) backward untaint removes the whole backward cone (`SPT_6_oneLP.als:349`), but p7 allows only "For register MOV instructions (r2 = r1): if the output is untainted, then the operand is untainted" and "For invertible arithmetic instructions (e.g., ADD): if the output is untainted and all but one of the inputs are untainted, then the remaining input is untainted" (SPT-2: per-instruction rules). (2) The STL untaint (`:357`) ignores STLPublic: p7 "STLPublic(S, L) holds if and only if L's address is untainted, and the addresses of all stores older than L and younger than S (including S) are untainted"; p8 Fig. 5 "Naive untaint propagation over store-to-load forwarding leaks tainted data" (SPT-3: gate on both addresses). (3) The final `^op_edges` closure (`:259/271/280`) re-taints what the STL rule untainted, against p7 rule ① "If S's data operand gets untainted, then L's output register should be untainted" (SPT-1: drop the closure term). (4) One forward pass in spo order, but p7 "untainting of a register by instruction I can cause instructions both younger and older than I to untaint registers" (run the 6-step fold 2–3 times).

**ReCon (`aimoniotis-2023-recon.pdf`, a 3-page extraction).** Paper: reveal happens only at commit of a direct load pair, p2 §5.2 "When the second load (LD2) of a load-pair commits, the address accessed by the first load (LD1) is marked as revealed", p1 §4.3 "RECON limits its detection to only the leakage of load pairs with a direct dependence"; conceal on store commit, p2 §5.2 "upon the commit of a store instruction, the bit of the corresponding word is cleared"; speculation sources, p1 §3.1 "For evaluation, we use only speculation cast by control flow and store instructions". Model: the reveal term in `hardware_protection_policy[p]` (`Recon_6.als:316-318`) only removes states the STT fold at `:323` already removes (R-1), so Recon_6 behaves as STT_6 minus `rf_from_most_recent_writer`. **Corroborated today:** Recon_6_core and STT_6_core give the same 2 cores at `but 3`, and their RI-only versions the same 129. Proposed (R-2, not applied): a single-hop reveal `fun revealed_p[p] : State { (Loads.inmem).opstate & (~opstate).((~inmem).(Loads & (rf_p[p].((Loads - speculation_contract_p[p]).inaddr)).~outreg)) }` with LD2 restricted to `committed_p`, a store-commit conceal, and instance-based untaint; plus a store-shadow contract if the build's threat model needs it.

## Runs (Stage 1 only, started 2026-11-03 03:19–03:20 PST, local Mac)

Free disk at start 88–94 GB (`df -h /System/Volumes/Data`). Runner: `STAGE1_alloy/models/proposed_twophase/run_stage1.py`, the repo's `a6CountModels` driver as `pipeline.py:phase_xml` calls it, `-Xmx4g`, cap 100000 (= `alloy.max_instances` in `runconfigs/*.jsonc`), timeout 21600 s (6 h), refuses to start under 50 GB free and kills java under 40 GB. The log records start/end, the exact command, the model sha256, the scope line, progress every 60 s, the verdict (`EXHAUSTED` = solver reached UNSAT below the cap = bounded-exhaustive at `but 6` up to symmetry=80; `CAPPED`; `TIMEOUT`; `DISK_GUARD`; `ERROR`) and the full java stdout/stderr.

| Model | Runner PID | java PID | Core file | Output (gitignored) | Log |
|---|---|---|---|---|---|
| STT_6 | 67090 | 67093 | `STAGE1_alloy/models/STT_6_core.als` | `testsets/STT_6__twophase_draft/stage1_xml/` | `~/Library/Logs/simspect/twophase_STT_6.log` |
| Recon_6 | 67091 | 67094 | `proposed_twophase/Recon_6_core.als` | `testsets/Recon_6__twophase_draft/stage1_xml/` | `~/Library/Logs/simspect/twophase_Recon_6.log` |
| SPT_6_oneLP | 67140 | 67142 | `proposed_twophase/SPT_6_oneLP_core.als` | `testsets/SPT_6_oneLP__twophase_draft/stage1_xml/` | `~/Library/Logs/simspect/twophase_SPT_6_oneLP.log` |

Launch command (one per model, from `STAGE1_alloy/models/proposed_twophase/`): `nohup python3 -u run_stage1.py --name <M> --model <core.als> --out <repo>/testsets/<M>__twophase_draft/stage1_xml --log ~/Library/Logs/simspect/twophase_<M>.log > ~/Library/Logs/simspect/twophase_<M>.nohup.txt 2>&1 &`. Monitor: `tail -f ~/Library/Logs/simspect/twophase_*.log` (look for `VERDICT=`), or `ls testsets/<M>__twophase_draft/stage1_xml | grep -c xml`. Kill: `kill <runner PID> <java PID>` (killing only the runner leaves java running; kill both, or `pkill -f a6CountModels`). The runner refuses to reuse a non-empty output dir; delete it to rerun. Stage 1.5 was not run; when a core set is in hand: `cd STAGE1_alloy && python3 stage_pipeline.py --core-model models/proposed_twophase/<X>_core.als --flesh-model models/<X>.als --out-xml-dir ../testsets/<X>__twophase_draft/xml` (note it re-runs Stage 1 itself; it doesn't yet accept existing cores).

## Open decisions for Anna

- [ ] DECIDE: approve, change or drop the drafts `SPT_6_oneLP_core.als` and `Recon_6_core.als` (diffs above), and whether `proposed_twophase/` is the right home (the dashboard's model table globs `STAGE1_alloy/models/*.als` non-recursively, so drafts and their runs are not visible there yet).
- [ ] DECIDE (D4, URGENT_TODO #2): Stage 1 minimality RO+RI (prototype, matches `pipeline.tex:45-58`) or RI-only (rebuilds in-use exactly at N=3, TWO_STAGE_STT_FEASIBILITY.md §9). New evidence: at `but 3`, RO+RI gives 2 STT/Recon cores vs 129 raw RI-only; RO deletes the STL mechanism outright (the store's `outmem` is required by `stl_alias_pair` but never on the leak path, so `secure[RO->s.outmem]` always fails: 0 at `but 3`, exhausted in 4 s); SPT gives 0 under both at `but 3`/`4`. Recommendation: RI-only if Stage 1.5 must reproduce the in-use corpora (and for STL it is the only option); RO+RI only if you want a smaller, different corpus.
- [ ] DECIDE: SPT's Stage 1. If the SPT run ends `TIMEOUT` with 0 cores, either SPT's one-leak-point clause plus RI/RO has no small solution, or the search is just slow. Options: (a) RI-only for SPT; (b) keep SPT flat (no Stage 1) until A1 / SPT-1..3 land; (c) a longer run on cafe2. Recommendation: wait for the run, then (a) with a longer bound.
- [ ] DECIDE: "bounded exhaustive" needs the Stage-1 verdict `EXHAUSTED`. Without idx symmetry-breaking even STT at `but 3` didn't prove UNSAT in 300 s. If the 6 h runs time out, accept "bounded, non-exhaustive" wording, or add a length-agnostic symmetry break to the cores (a model change).
- [ ] DECIDE: the cores copy `rf_from_most_recent_writer` verbatim, so STT_6_core has it and the SPT/Recon drafts don't (same open item as `URGENT_TODO.md:31`). Align all models (and cores) before any staged campaign?
- [ ] DECIDE: Recon_6_core equals STT_6_core in practice (R-1). Run Recon's Stage 1/1.5 at all before the R-2 reveal rewrite?
- [ ] DECIDE: draft two-phase versions for the variants too (STT_6_stl needs RI-only; STT_6_commitsplit / _futuristic after their reviews)?
- [ ] DECIDE: the paper disagreements above (STT-1, STT-3, SPT-1..3, R-1/R-2) are existing items in `URGENT_TODO.md:74-76`; any fix there changes the production model and the core together (re-run `derive_core.py`).
- [ ] TODO (not a decision): fix the stale comment in `STT_6_core.als:279-289` when you next touch it (it claims idx is kept).

## 2026-11-07 — RESOLVED: why SPT Stage-1 produced 0 (and it is NOT RO over-pruning)

The 6 h Stage-1 runs finished (2026-11-03): STT_6 → 2 skeletons, Recon_6 → 2, **SPT_6_oneLP → 0** (`VERDICT=EXHAUSTED`, genuine UNSAT, no crash). Anna asked for the root cause: is SPT mis-modeled, or does the SPT case need a different minimality rule. Investigated 2026-11-07 (deep-dive session); evidence below is reproducible.

**Isolation sweep (scratch copies outside `models/`, scope 5, cap 150; STT as control):** each perturbation applied alone.

| variant | STT (control) | SPT |
|---|---|---|
| base (no RO/RI; RR+RC+RS only) | 150 (capped, 5 s) | **150 (capped, 17 s)** |
| RI-only | 129 | **0** |
| RO-only | 67 | **0** |
| RO+RI | 2 | **0** |

**Finding 1 — it is not RO.** For SPT, **RI-only *and* RO-only each independently give 0**; RR/RC/RS necessity (present in the base run) are fine. So the earlier "RO over-prunes" framing (`RIONLY_BASELINE_PROOF.md`) is the wrong diagnosis for SPT: *no* SPT leak is minimal under removing *any* instruction *or* *any* operand, even though SPT base leaks are abundant (150+). STT is non-zero under every rule. This is SPT-specific and structural.

**Finding 2 — it is not the base-predicate mismatch.** SPT's base is `one_insecure_speculation_scheme_p` (exactly one leaker) while necessity is tested with `secure_speculation_scheme_p` (zero leakers); STT uses `not secure_speculation_scheme_p` (≥1) for both. Swapping SPT's base to STT's `not secure` form **still gave 0** under RI-only / RO-only / both (scope 5). So the mismatch is not the cause.

**Finding 3 — root cause (strongly supported, one confirmation step pending): SPT's protection-set *seed* is unperturbed and computed over the *whole* program.** `SPT_6_oneLP.als:341` — `fun hardware_protection_policy: Operand {Instruction.operands - ((Inreg + Inaddr) - Instruction.outreg.rf)}` — has no `[p]` parameter and references the full `Instruction`/`Instruction.outreg.rf`. So when RI removes an instruction (or RO an operand), the protected set does **not** shrink: the transmitter stays protected, so the leak survives almost every removal → no leaking instance is minimal → UNSAT. STT avoids this because its seed is `STT_6.als:326` `fun hardware_protection_policy: State {Mem_s}` — a pure sig, genuinely independent of which instructions exist — and *all* instruction-sensitivity lives in the **perturbed** `prot_set_propagation_p[p,…]`, so removals do shrink STT's protection and minimal instances exist. This is the same operand-based seed already flagged as the A1 protection-set issue (`wiki/findings/mdsToRead/PROTECTION_SET_REEVAL.md`). *Pending confirmation:* build an SPT variant with a perturbation-aware seed `hardware_protection_policy_p[p]` (over `i_p[p]`) and check RI/RO necessity becomes SAT — this is a semantics change, so it needs Anna's sign-off before trying.

**Consequence for the two-phase build.** The RO+RI "most-minimal skeleton" Stage-1 is **incompatible with SPT's current model** — not fixable by dropping RO (RI-only is also 0). STT/Recon are unaffected (2 cores each). Options for SPT, Anna-leaning-conservative ("over-generate, rule out"): (1) SPT Stage-1 = **no removal-minimality** (base + RR/RC/RS only, capped + dedup) → over-generates, works today; (2) **scope-ladder minimality** (enumerate N=3..6, dedup by fingerprint, keep smallest distinct shapes) → small cores without the broken removal test; (3) **fix the seed** to be perturbation-aware (Finding 3 / A1 rework) → correct long-term, changes SPT semantics, needs approval. Decision is Anna's; see URGENT_TODO.

**2026-11-08 — conservative run done (option 1, Anna-approved "simplest, run ASAP").** New file `STAGE1_alloy/models/proposed_twophase/SPT_6_oneLP_core_conservative.als` = SPT core with the RO (line 314) and RI (line 317) clauses commented; base `one_insecure` + RR/RC/RS untouched; scope `up to 6`. Enumerated **20000 instances (CAPPED at 20000)** in ~12 min → `testsets/SPT_6_oneLP__twophase_draft_conservative/stage1_xml/` (host MacBook-Pro-146, local). Confirms at full scope that no-removal-minimality over-generates heavily (full set > 20000). This is SPT's Stage-1 corpus for round 2 until/unless the seed fix (option 3 / A1) is done. No existing `.als` edited.

## 2026-11-08 — STL split cores (stl-spec session)

Each main model now has an STL draft (`STAGE1_alloy/models/MANIFEST.md`, `wiki/design/STL_SPECULATION.md` "STL for every main model"), and each STL model has a Stage-1 core draft made by `derive_core.py`. No existing file in this folder was edited.

| Core draft | From | Minimality | Small-scope check | Stage-1 run |
|---|---|---|---|---|
| `proposed_twophase/STT_6_stl_core.als` | `STT_6_stl.als` (approved) | RI-only (`--minimality ri`; RO+RI is UNSAT for STL by construction, D4 evidence above) | 200 (capped) at ≤3 in 12 s, at ≤4 in 67 s | **EXHAUSTED: 306 cores at ≤6** (13:58–14:20): `testsets/STT_6_stl__twophase_draft/stage1_xml`, log `~/Library/Logs/simspect/twophase_STT_6_stl.log` |
| `proposed_twophase/Recon_6_stl_core.als` | `proposed/Recon_6_stl.als` (draft) | RI-only | 200 at ≤3 in 31 s, at ≤4 in 165 s | started 2026-11-08 13:58, same settings: `testsets/Recon_6_stl__twophase_draft/stage1_xml`, `twophase_Recon_6_stl.log` |
| `proposed_twophase/SPT_6_oneLP_stl_core_conservative.als` | `proposed/SPT_6_oneLP_stl.als` (draft) | none (RI line commented, the SPT conservative convention) | UNSAT at ≤3 and ≤4: SPT's RS-minimality conflicts with the alias fact (see the STL doc) | not run (nothing to enumerate until the RS DECIDE) |

The RI-only cores are not small: both hit the 200 cap at ≤3, unlike the RO+RI STT_6 core (2 cores). That is the known RI-only trade-off (#2). Stage 1.5 for these cores waits on the Stage-1.5 machinery, which isn't built for any family yet.
