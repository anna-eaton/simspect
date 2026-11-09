<!-- Paste everything below this comment at the end of wiki/design/TWO_PHASE_MODELS.md, then delete this file. It is here only because wiki/ and Bash returned EPERM at the end of the stage15-bound session. -->

## Stage 1.5: looser skeleton and larger bounds (2026-11-08)

stage15-bound session, for Anna's question: "For the second phase pin: I want it to be able to have a LOOSER skeleton with MORE INSTRUCTIONS. Can that be done, so we can increase the bound?" Tooling, cores and raw results: `STAGE1_alloy/models/proposed_twophase/stage15_bound/` (README there). The runs were on cafe2 `gem5_dev`, workspace `/tests/stage15_bound_20261108/`, with 4 to 6 JVMs at a time, 1500 s per job, and a 3-minute enumeration window unless noted. No existing `.als` was edited, and simspect-c8's runs were not touched. Every model that was measured is in `<ws>/bench/models/<job>.als`, and the full results are in `<ws>/bench/results.jsonl`.

### Answer

**Yes for STT and Recon up to about 10 to 12 instructions, and for SPT up to 8 (10 only with a re-encoded fold). It needs four mechanical edits to the skeleton, and a looser pin is what makes the new instructions useful.** The current pin (every core edge fixed) can never put an ALU on the core's path or build the OTB precursor; both queries are UNSAT. The "path pin" (b) below can, at N = 6, 8 and 10. Growing N alone mostly adds padding (operand-free branches), so a no-padding rule and forcing predicates are part of the design.

### What in the skeleton is semantic, what only shapes the search, and what must scale with N

- **Semantic, keep as is:** the defense block, rf/ddi/spo meaning, the perturbation functions, `secure_speculation_scheme_p`, `tag_xm`, `no_extra_ops`, the operand-kind facts.
- **Semantic but tied to N, so it must be regenerated (mechanical edits):**
  - (S1) The protection-set fold `last_committed_protset_p` is unrolled 7 deep (`STT_6.als:232-243`, `SPT_6_oneLP_v2.als:256-267`, `Recon_6.als:222-233`), so it only visits spo positions 0-6. Query `fold_trunc` asks whether the 7-deep fold reports a leak that the N-deep fold calls secure. It is **SAT for STT_6 at N=10 (17 in 30 s), SPT v2 at N=8 (11) and Recon_6 at N=10 (6)**. So past 7 instructions the unedited model invents leaks. For STT at N=8 there was no instance in 1500 s; STT needs a non-speculative load at position ≥7 followed by a branch and the transmitter, so N ≥ 10.
  - (S2) IX symmetry-breaking has 6 atoms in a bijection (`STT_6.als:37-48,280-295`), so with `exactly N` and N > 6 the model is UNSAT by pigeonhole. It has to be regenerated for N or dropped.
  - (S3) **Int bitwidth.** The skeleton's caps are cardinality facts (`limited_inregs`/`inaddrs`/`ins`/`outs`, `STT_6.als:122-126`) under Alloy's default 4-bit Int (−8..7, overflow allowed). Once more than 9 operands are in scope, one instruction can carry 8 or more operands; `#` wraps to a negative number and the cap passes. Measured with `overflow_scan.py`: **74/300 instances already break the caps at N=6 with 12 operands, and 280-298/300 at N=7-12 with 2N operands** (one instruction carried up to 18 inputs). At the production scope (`for 9`, at most 9 operands) the count is 0/300 in every family, so the running exactly-6 Stage 1.5 is unaffected. The fix is `6 Int` in the scope. All N > 6 numbers below use it; earlier 4-bit runs at larger operand scopes are contaminated, except their UNSAT results, which stay valid because overflow only weakens the facts.
  - (S4) **The `for 9` Operand cap must grow.** At N=10 with 9 operands, about 5 of the 10 instructions are operand-free branches (census). I used 2N operands. State does not need to grow: RS-minimality keeps every sample at 3 or fewer states and 3 or fewer Reg_s.
- **Search-shaping only, can be loosened:** the exact-N scope, IX, `no_extra_inst` (it exempts Branchn, which is where the padding comes from), and the Stage 1.5 minimality clauses (RR, boundary RC+RR, RS).

### Looser pins and their soundness

| pin | what is pinned | still a real leak under the model? | contains the core? | can host an ALU on the path / OTB precursor? |
|---|---|---|---|---|
| (a) current (`stage_seed.py`) | every core instruction, operand, flag, ddi and rf edge; spo relative | yes: the production `gen_useful_litmus` (`not secure[no_p]` + RR/RC/RS) is in every run | yes, as a subgraph | **no**: `splice_xm` UNSAT (STT N=8, 1147 s); `otb_shape` UNSAT (STT N=8 80 s, SPT N=8 51 s, Recon N=8 8 s) |
| (b) path pin | as (a), but each core rf edge `ob in oa.rf` becomes `ob in oa.rf.*(ddi.rf)`, so it may be split through added instructions (ALU, or a store→load hop) | yes, same argument: the leak predicate is evaluated on the whole new program, so an added instruction that declassifies (SPT, ReCon) removes the instance instead of hiding a non-leak. This is the advantage over Stage-2 splicing. | yes, as a topological minor (edges become paths). The leak may also arrive through an added merge input, which is the OTB shape. | **yes** (below) |
| (c) leak pin | only xm's kind and an unresolved branch of the core's kind before it | yes | no; this is flat enumeration at N, split by (xm kind, branch kind) | yes, but nothing ties it to a core, so per-core balancing is lost |

`splice_xm` (an ALU on the core's rf edge into xm's leak operand) with pin (b): **SAT** for STT ld/br_x and Recon at N=6 (1500-1900 instances in 60 s); SPT k3 at N=6 is EXHAUSTED at 180; STT at N=8 gives 264 in 60 s and at N=10 36; SPT at N=8 gives 14. `otb_shape` (the precursor from `OTB_GENERATION_GAP.md:8`, an ALU outreg rf-feeding a load transmitter's inaddr) with pin (b): **SAT** for STT at N=6/8/10 (1506, 73 and 56 per window), Recon at N=6/8 (1142, 25) and SPT at N=6/8 (EXHAUSTED at 180, 10). Unforced, the first 300 instances of pin (b) have **0% ALU on the transmitter path** (census, N=6-12). This is the same order artifact as OTB: the shapes exist but enumeration reaches them only when forced.

### Measurements (core = one Stage-1 RI core; `inst/min` = instances in the 3-min window after the first)

| family / core | pin | N | scope | translate (s) | first (s) | inst/min | CNF clauses | notes |
|---|---|---|---|---|---|---|---|---|
| STT_6 ld (k3 #5) | a | 6 | production `for 9` | 1.2 | 2.0 | 2110 | 154k | baseline = running Stage 1.5 |
| STT_6 ld | b | 6 | +6 Int | 1.5 | 2.4 | 2050 | 162k | path pin costs nothing |
| STT_6 ld | b | 8 | 16 Op, 6 Int | 3.1 | 7.3 | 549 | ~0.7M | |
| STT_6 ld | a / b | 10 | 20 Op, 6 Int | 7.0 / 7.5 | 13.5 / 14.0 | 229 / 157 | ~1.5M | |
| STT_6 ld | b | 12 | 24 Op, 6 Int | 15.5 | 34.7 | 57 | ~2.6M | |
| STT_6 ld | b + nospacer | 10 / 12 | 6 Int | 7.2 / 15.5 | 17 / 139 | 183 / 13 | | padding banned |
| Recon_6 ld (k3 #5) | a | 6 | production | 0.9 | 1.7 | 1698 | 222k | larger scopes ≈ STT (4-bit runs only) |
| SPT v2 ld (k3 #30) | a / b | 6 | production | 9.8 / 9.6 | 11.4 / 10.7 | 761 / 797 | 356k | |
| SPT v2 ld | b | 8 | 16 Op, 6 Int | 38.8 | 44.2 | 169 | 1.5M | nested fold |
| SPT v2 ld | b | 10 | 9 Op (no overflow) | **539** | 544 | 370 | 0.6M | nested fold, ×3.7 per extra position |
| SPT v2 ld | a, b | 12 | 24 Op | **>1500 (timeout)** | — | — | — | stuck in Kodkod "optimizing bounds and formula" |
| SPT v2 ld | b, explicit fold | 10 / 12 | 6 Int | 7.1 / 14.1 | 20 / 60 | 10 / 3.3 | | translation fixed, solving slow |
| SPT v2 ld | b, explicit, nospacer | 10 | 6 Int | 7.8 | 165 | 4.7 | | |

Peak JVM heap stayed at or below 3.1 GB in every run, so the production `-Xmx4g` fits. **SPT's blow-up is the nested fold.** SPT's `prot_set_propagation_p` uses its accumulator `o` four times (`SPT_6_oneLP_v2.als:379-396`), while STT and Recon use it once (`STT_6.als:329-332`). The formula therefore grows roughly 4^N (8→9→10: 38 s, ~140 s, 539 s), and a `let` binding did not help (139 s vs 149 s at N=9, `<ws>/letprobe/`). The **explicit fold** (`make_s15_model.py --fold explicit`) replaces the nesting with one relation per perturbation form (`PSX.pn/prr/prs/prc`, defined step by step along spo). It is exact at any N and valid whenever no RI perturbation is used, which holds for every Stage 1.5 run. Equivalence with the nested fold (`fold_equiv`, facts only): **UNSAT (the encodings agree) for STT_6 at N=10 (638 s) and Recon_6 at N=8 (512 s)**; for SPT at N=6/8 and STT at N=6 there was no counterexample in 1500 s, so it is not proven. For STT the explicit fold is slower to enumerate (19 vs 57-97 per minute at N=12), so use it only for SPT.

**Budget arithmetic (one core per JVM, 24 JVMs as in simspect-c8's Stage 1.5):** 300k STT instances at N=10 is 300000 / (157 × 24) ≈ 80 min; at N=12 it is ≈ 3.7 h, or ≈ 16 h with nospacer. SPT at N=10/12 (3-10 per minute per core) supports only small per-core caps, about 10-50.

### Stage 2 and hooks at larger N

100 XMLs each from STT N=6 pin (a), STT N=10 and N=12 pin (b), and SPT N=10 pin (b), run through the repo's unchanged `batch_generate.py` (both modes, plain and fanout v2 from `specs/fanout/stt.json`) and `compile_annotate.py`: **100/100 `.ll` and 100/100 `.s`+`.ann` in every case** (`<ws>/stage2/summary.json`). Caveat: these XMLs came from the 4-bit models, so a few instructions may carry extra operands; re-run `stage2_check.py` on 6-Int XMLs before relying on it. Register pressure does not scale with N: RS-minimality keeps Reg_s at 1-3 in every sample, and pass 3 allows up to 10 locked registers (13 in `X86_64_CALLER_SAVED`, 3 reserved, `parsexml.py:1407-1427,1538-1568`). Branch annotations are list-valued SimObject params with no fixed size (`gem5-hooks/stt/se_exp.py:67-100,288-293`), and pin (b) keeps a single unresolved branch. The window is not a limit either: `unresolved_stall_cycles: 5000` in the run configs keeps the branch unresolved long past 12 Alloy instructions, so the ROB is the bound.

### S4 / A3c (s4-variant's shapes) under these designs

The pin and the bound do not unblock S4 or A3c; minimality does. With the production minimality and pin (b): S4 and A3c are UNSAT at N=6 (5 s, 9 s) and S4 is UNSAT at N=8 (1441 s). A3c at N=8/10 and S4 at N=10 gave no instance in 1500 s. With `leak_rs` (Stage 1.5 keeps only the leak and RS, and drops RR and the boundary clause), both are **SAT** at N=6 (about 1000 in 30 s each), at N=8 with 6 Int (364 and 459 in 60 s), and at N=8 even with pin (a). The cost: without RR, irrelevant unresolved branches pile up (up to 4 per instance at N=6, against 1 under the production minimality).

### Anna's two routes for minimality

- **(a) Smarter minimality: recommended, as "core-relative minimality".** The core already proves the leak is minimal, so Stage 1.5 does not need to re-prove it over the whole program. Keep the leak, RS (state sharing, the paper's round-2 rule) and RR/RC on the core's own instructions only. Each added unresolved branch must instead meet a cheap relevance test: its predicate is data-dependent on a load (S4's B1), it is younger than xm (A3c's B2), or it is the resolved boundary branch (S4's B0). That generalizes s4-variant's two one-off exemptions into one rule and stops the branch pile-up that `leak_rs` shows. It is not measured yet; it is a model-text change.
- **(b) More bounded random enumeration.** SAT4J enumeration is deterministic and order-biased (0/300 ALU-on-path unforced), so a larger cap alone does not make it random. Randomness has to come from outside: forcing-predicate partitions (one per shape: plain, splice, OTB, S4, A3c, the way Stage 1 already partitions by k × kind), random per-core caps, or `STAGE1_alloy/a6DiverseModels.java` (present, not evaluated here). (b) is cheap to try with today's tooling; (a) is what removes the systematic blind spot.

### OTB now

Pin (b) produces the OTB precursor directly in Alloy for STT, Recon and SPT at N=6-10 (numbers above), and pin (a) provably cannot. The full `getOldestTaint` merge also needs the ALU's *second* input to come from a different tainted load under an earlier-resolving branch. That is one more forcing predicate on top of `otb_shape`, which I did not run: `some o: Otherns+Otherxs, disj l1, l2: Loads | some (o.inreg & l1.outreg.rf) and some (o.inreg & l2.outreg.rf) and some (o.outreg.rf & xm.inaddr)`. Fastest route: a Stage 1.5b partition "pin (b) + otb merge" at N=8 for STT_6/Recon_6.

### If the looser pin were not used: Anna's fallback

Looser randomization in Stage 2 (fanout v2 splices and fillers already exist; add random extra branches and loads), then an after-the-fact check per concretized test. Re-encode each final program as a fully pinned Alloy instance (every instruction, operand and edge fixed, so no search) and evaluate `not secure_speculation_scheme_p[no_p]` with the N-deep or explicit fold, plus the forcing predicate of the intended shape. Each check is a single instance check, about the cost of one translation (seconds at N ≤ 12 for STT, and for SPT with the explicit fold). Tests that fail are labelled "not a model leak" instead of being run. This is sound but blind: it only checks what randomization happened to produce, so S4/A3c/OTB still need to be targeted.

### Recommendation (mine, for Anna to decide)

Keep the running exactly-6 Stage 1.5 as the base corpus (it is unaffected by the issues found here). Add a **Stage 1.5b at N=8** (STT_6/Recon_6 up to 10) built from the production model plus the four scope edits (fold regenerated N deep, IX regenerated, `6 Int`, 2N operands), **pin (b)**, **no-padding** (every instruction has an operand), and minimality = **core-relative** once written (until then, the production minimality plus separate forced partitions for S4/A3c with `leak_rs`). Enumerate it as forced partitions per core (plain / splice_xm / otb merge / S4 / A3c) with small per-core caps. SPT: N=8 with the nested fold; beyond that only with the explicit fold and caps of about 10-50 per core.

### Decisions for Anna

- [ ] DECIDE S15-1 (bound): Stage 1.5b at (i) N=8 for all families, (ii) N=10 for STT/Recon and 8 for SPT, or (iii) none (stay at 6 and use the fallback). Recommendation: (ii).
- [ ] DECIDE S15-2 (pin): (a) current, (b) path pin, or (c) leak pin. Recommendation: (b), the only one that hosts ALU-on-path/OTB and still contains the core.
- [ ] DECIDE S15-3 (padding): none, nospacer, or connected (every non-branch instruction linked to xm's dataflow; written in `make_s15_model.py`, not measured because the run was cut by the Int finding). Recommendation: nospacer.
- [ ] DECIDE S15-4 (minimality in 1.5b): production, core-relative (to be written), or `leak_rs`. Recommendation: core-relative; production plus forced S4/A3c partitions until it exists.
- [ ] DECIDE S15-5 (approve the scope-tied `.als` edits for any N > 6 draft): fold depth ≥ N, IX for N, `6 Int`, Operand scope. They are mechanical, and without them the model is wrong (S1, S3) or UNSAT (S2).
- [ ] DECIDE S15-6 (SPT encoding): adopt the explicit fold for SPT N > 8 (equivalence for SPT not yet proven, only no counterexample in 25 min), or cap SPT at 8.
