# Pending Alloy model changes (owner-gated) — block out known-issue false positives

*Living doc, overwrite-in-place. The single consolidated list of `.als` edits we've concluded we
need, each one grounded in a findings doc. **Nothing here is applied** — every `.als`/`parsexml.py`
edit needs Anna's explicit per-change sign-off (root `CLAUDE.md` → Alloy models STRICT). This file is
the backlog + rationale so the edits don't live only in scattered findings mds.*

**Last refreshed:** 2026-11-09 (ultimate ReCon/SPT sections at the bottom, ultimate-recon-spt; model-fixes drafts + blind-spot backlog at top; STT_6_s4 / STT_6_a3c drafts at top; SPT conservative fix plan below)

---

## 2026-11-08 — model-fixes: `STT_6_v2` / `Recon_6_v2` / `SPT_6_oneLP_v3` drafts + the rf-fact patch (DRAFTS, unapproved; written up 2026-11-09 by session main-1109 from the model-fixes agent's saved queries)

**Superseded by the full section right below** ("model-fixes: instance-based STT/ReCon protection…", written by the model-fixes agent with every exact diff, query, time and decision). Corrections to this summary (checked against `STAGE3_gem5/triage/model_audit_20261108/queries/model_fixes_runs.log`): `t4_lost_complete` and `t1_lost_complete` **timed out (900 s) with no instance**, they were not UNSAT; the `t1_mono*`/`t4_mono` queries were stopped (the subset argument is in the full section), not UNSAT; of the 7 rf-patched copies, 5 are SAT and the two SPT STL files generate nothing before or after the patch (known RS-vs-alias conflict). The blind-spot table below is main-1109's and stands.

### Model blind spots → hole classes the pipeline cannot find today (robustness backlog, 2026-11-09)

Each row is a construct none of the three models (or the Stage-2 vocabulary) can express, the by-reading holes it hides, and the smallest change that makes the class generable. Source: the 2026-11-08 audits plus the queries above; nothing here is verified in gem5 unless the audit says so.

| Blind spot | Hides (by reading) | Smallest fix |
|---|---|---|
| Registers are whole values (no width / byte taint) | SPT A3 (partial write leaves merged upper bytes public) | Stage-2 vocab: 8/16-bit `mov`/`movzx` fillers on the transmitter chain; model stays whole-value, `check_ld` catches it |
| No flags operand | SPT A1 (`inc` after `cmp secret`), SPT A2 (`cmov`), any `adc`/`sbb`/`setcc` data flow in STT/ReCon | vocab: flag-consuming ALU ops (`br_cmp` work in flight); model: a flags `State` written by `cmp`/`add` |
| No FP/vector register class | STT S1 (confirmed), ReCon R-SA-13 | fp corpus `testsets_latest/STT_6_fp` (exists, running) |
| One data chain into the transmitter | OTB / R-SA-8 (`getOldestTaint`) | Stage 1.5 OTB pin or fanout-v2 OTB splice (fpr-fanout round 3) |
| Store→load forwarding is just an rf edge | recon A2 shadow, R-SA-9, the SPT v3 residual above | `store_separation` option (done) + Option B for SPT |
| No access width / alignment | ReCon R-SA-3/4/5, SpecLFB SL-1, DoM R-SA-14 | sub-word and misaligned loads (parked by Anna) |
| Reveal needs a committed LD1→LD2 pair | all ReCon R-SA-2..6 (now testable on `/work/gem5-recon-ruby3`) | Stage 1.5 pin: a share of instances must satisfy `some revealed_p` |
| Only branch speculation | store-shadow bugs (STL round), E-shadows / faults (out of contract) | STL models exist; faults stay out |
| Taint lives in registers only in the model; gem5 also has per-phys-reg quirks | STT S1, ReCon R-SA-12 (phys int reg 16), R-SA-7 (stale taint entries) | random register naming (default now) + reg-16 diagnostic (approved) |

---

## 2026-11-08 — model-fixes: instance-based STT/ReCon protection, the ReCon reveal rule, rf fact everywhere, SPT v3 (DRAFTS; sign off per diff)

**Bottom line.** Four changes, each validated with Alloy queries (scratch copies under `STAGE3_gem5/triage/model_audit_20261108/queries/mf/`) and cross-checked with an independent Python re-implementation of the semantics (`STAGE3_gem5/triage/model_audit_20261108/mf_semantics.py`). No existing `.als` was edited: the rf-fact patches for the 7 in-use files are built and checked but **not applied** (see C; the agent was told Anna authorized it, but only Anna's own message or the permission prompt counts as approval for an in-place `.als` edit, so the apply step is a one-line script for her).

| ID | File (new unless noted) | What it changes | Validation in one line | Anna signs off |
|---|---|---|---|---|
| A | `STAGE1_alloy/models/proposed/STT_6_v2.als` (sha256 1ad8c5a9…) | protection = the memory read of every **speculative load** (instance-based), not "every location no non-speculative load read" | QR1a UNSAT → **SAT**, QR1c SAT → SAT; 3000-instance differential: 0 lost, 114 gained (3.8%), every gained instance is the R-1 shape | diff A |
| B | `STAGE1_alloy/models/proposed/Recon_6_v2.als` (sha256 edda1bcc…) | A + `rf_from_most_recent_writer` + a new reveal: direct load pair, LD2 **committed**, per word, concealed by any store to the word in between | (a) UNSAT, (b) SAT ×4, (c) SAT, (d) protection set now differs from STT's (SAT; was UNSAT in QR2) and 300/300 Recon-only + 300/300 STT-only samples explained | diff B, plus DECIDE B1-B3 |
| C | 7 existing in-use files (NOT applied) | insert `rf_from_most_recent_writer` verbatim from `STT_6.als:161-169` | patched copies parse; `gen_lit` SAT for 4/7, see table for the other 3 | run `apply_rf_fact.sh` |
| D | `STAGE1_alloy/models/proposed/SPT_6_oneLP_v3.als` (sha256 6b2a0948…) | audit S-1 Option A: declassification also removes the producer load's `Inmem` | Q1 SAT → SAT (only via a store→load rf into the declassified load; **UNSAT once that is excluded**); lost differential = 300/300 S-1 shapes; RI cores at `but 3`: 546 → 393, the 153 removed are exactly the S-1 cores | diff D (Option A approved by Anna for now), DECIDE D1 |

Stage-1 cores derived mechanically with `proposed_twophase/derive_core.py --minimality ri` (same three changes as every other core, nothing else): `proposed_twophase/STT_6_v2_core_ri.als` (75cf0e26…), `proposed_twophase/Recon_6_v2_core_ri.als` (d24c95ed…), `proposed_twophase/SPT_6_oneLP_v3_core_ri.als` (c024293f…). Generator for the three drafts (asserted, anchor-exact replacements, refuses to overwrite): `STAGE3_gem5/triage/model_audit_20261108/make_v2_models.py`.

### A. STT_6_v2: instance-based protection (fixes audit R-1 / STT-3 / Recon F2)

**What was wrong.** `STT_6.als:331` removes the *location* (`inmem.opstate`) of every load with no unresolved older branch from the protection set, which is a set of `State`s. So once a non-speculative load reads word A, every later operand on A is public, including a *speculative* re-load of A that feeds a transmitter. STT says the opposite: "If a load is unsafe, its output is always tainted" (`yu-2019-stt.pdf` p6, §"Visibility point"; checked with `pdftotext` this session). The audit's QR1a (that re-load feeding a load transmitter, no load pair) was UNSAT on STT_6 and Recon_6 and its control QR1c (different location) SAT.

**The change, in plain words.** The protection set becomes a set of operands. Its seed is the `Inmem` of every speculative load (`(Loads & speculation_contract_p[p]).inmem & o_p[p]`), and nothing is ever removed in program order (propagation = identity). Taint still reaches a load's output over its `Inmem → Outreg` ddi edge and flows on over rf+ddi through the existing transitive check. Four skeleton lines that read the set (`a`, `last_committed_protset_p`, `secure_speculation_scheme_p`, `tag_xm`) change type from `State` to `Operand`, i.e. they drop the `.(~opstate)` lift; this is the same Operand form `SPT_6_oneLP_v2.als:256-315` already uses, so the three model families now share one Operand-typed skeleton. **This is a skeleton edit (four lines), not just the defense block; there is no State-typed way to protect one load's read of A but not another's** (DECIDE A1).

**Kept on purpose.** A speculative load with no `Inmem` in the instance is still unprotected (as in STT_6): seeding its `Outreg` too would make every `Inmem` RS-unnecessary and shift the corpus to loads without memory reads. The equivalent shape with `Inmem` is generated, so nothing is lost in coverage.

```diff
--- a/STAGE1_alloy/models/STT_6.als
+++ b/STAGE1_alloy/models/proposed/STT_6_v2.als
@@ -1,3 +1,15 @@
+// =============================================================================
+// STT_6_v2.als — DRAFT, NOT APPROVED (2026-11-08, session model-fixes).
+// Derived from STT_6.als (sha256 7a6ac4c0a098c4dc0e24a4a1bbf867f1266c491b64bdd356026ec017d5b4198c), which is unchanged.
+// Changes, each marked [v2-n]; every other line is byte-identical to STT_6.als:
+//   [v2-2] instance-based protection set (defense clauses 2+3 of the block, plus the
+//          State->Operand retyping of the four skeleton lines that read the set:
+//          a, last_committed_protset_p, secure_speculation_scheme_p, tag_xm; same
+//          Operand form SPT_6_oneLP_v2.als already uses). Seeds = the Inmem of every
+//          speculative load; propagation = identity. Fixes audit R-1 (QR1a UNSAT).
+//   ([v2-1] rf_from_most_recent_writer is already in STT_6.als.)
+// Review + evidence: wiki/state/ALLOY_MODEL_CHANGES.md "2026-11-08 — model-fixes".
+// =============================================================================
 
 
 /*********************************************************************************
@@ -228,15 +240,15 @@
 
 fun speculative_xmit_p[p: PTag->univ] : Operand {leakage_function_p[p] <: speculation_contract_p[p].operands}
 
-fun a[p:PTag->univ,i:Instruction,s:State] : State { prot_set_propagation_p[p,i,s]}
-fun last_committed_protset_p[p: PTag->univ] : State {
+fun a[p:PTag->univ,i:Instruction,o:Operand] : Operand { prot_set_propagation_p[p,i,o]} // [v2-2] Operand-typed protection set
+fun last_committed_protset_p[p: PTag->univ] : Operand { // [v2-2]
 		a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
 a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
 a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
 a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
 a[p,f[p].(spo_p[p]).(spo_p[p]),
 			a[p,f[p].(spo_p[p]),
-				a[p,f[p],hardware_protection_policy]
+				a[p,f[p],hardware_protection_policy[p]] // [v2-2]
 			]
 	]
 ]]]]
@@ -260,16 +272,18 @@
 }
 
 pred secure_speculation_scheme_p[p: PTag->univ] {
-	(no (last_committed_protset_p[p].(~opstate) & speculative_xmit_p[p])) and
-	(no last_committed_protset_p[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p])
+	// [v2-2] the protection set is a set of operands now, so no .(~opstate) lift (same form as SPT_6_oneLP_v2.als:287-296)
+	(no (last_committed_protset_p[p] & speculative_xmit_p[p])) and
+	(no last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p])
 }
 
 // make sure there is some overlap in the end btw xm and speculative xmit
 //fact tag_xm {some xm & speculative_xmit_p[xm]}
 fact one_xm {#(xm) = 1}
 fact tag_xm { 
-	(some (last_committed_protset_p[no_p].(~opstate) & speculative_xmit_p[no_p] & xm.operands)) or
-	(some last_committed_protset_p[no_p].(~opstate).(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands)
+	// [v2-2] Operand-typed, as in secure_speculation_scheme_p
+	(some (last_committed_protset_p[no_p] & speculative_xmit_p[no_p] & xm.operands)) or
+	(some last_committed_protset_p[no_p].(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands)
 }
 
 /*********************************************************************************
@@ -323,11 +337,18 @@
 
 //fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & (no_unresolved_brs_p[p] + no_unresolved_mem_p[p])}
 fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}
-fun hardware_protection_policy: State {Mem_s}
+//fun hardware_protection_policy: State {Mem_s}
+// [v2-2] instance-based protection: the memory read of every SPECULATIVE load is a taint source,
+// whatever any other load did to the same location. STT (yu-2019-stt.pdf p6): "If a load is unsafe,
+// its output is always tainted"; the taint reaches the load's output over its Inmem->Outreg ddi edge.
+fun hardware_protection_policy[p: PTag->univ]: Operand {(Loads & speculation_contract_p[p]).inmem & o_p[p]}
 //fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}
 fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
-fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State {
-	// s - (Loads & committed_p[p] & i).inaddr.opstate // committed loads remove their inaddr from the protset
-	s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate // loads that have no unresolvd brs before them remove their inaddr from protset (acc load is not branch so probs chill)
+fun prot_set_propagation_p[p:PTag->univ,i:Instruction,o:Operand] : Operand {
+	// [v2-2] nothing is ever de-protected in program order: the seed is already the final set
+	// (old, location-based: s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate, i.e. any
+	//  non-speculative load made its whole LOCATION public, so a later speculative re-load of the same
+	//  word was never a leak; audit R-1 / QR1a, STT-3 / Recon F2)
+	o
 }
 
```

**Validation (Alloy, `exactly 6`; "facts only" = minimality off, as the audit ran QR1).**

| Query | Model | Form | Result (time) | Meaning |
|---|---|---|---|---|
| QR1a | STT_6_v2 / Recon_6_v2 | facts only | **SAT / SAT** (0 s / 1 s) | was UNSAT / UNSAT: the R-1 shape now exists |
| QR1c | STT_6_v2 / Recon_6_v2 | facts only | SAT / SAT (1 s / 1 s) | control unchanged |
| QR1a | STT_6_v2 / Recon_6_v2 | with gen | **SAT / SAT** (1 s / 1 s) | the R-1 shape is now generated, e.g. `ld [M0]` (C) ; br (U) ; `r0 <- ld [M0]` ; br ; `ld [r0]` = xm |
| QR1c | STT_6_v2 / Recon_6_v2 | with gen | UNSAT / UNSAT (1 s / 7 s) | as before: RS-minimality rejects the control's unused location |
| t1_gained | STT_6_v2 + old defense | gen, "new-useful and not old-useful", cap 300 | 300 (cap, 20 s) | all 300 explained (below) |
| t1_lost | STT_6 + new defense | gen, "old-useful and not new-useful", cap 300 | **0 found in 1500 s** (timeout, no counterexample) | see the argument below |
| t1_gained_complete | STT_6_v2 + old defense | facts only: xm flagged by new, not by old, and no R-1 witness on xm | **UNSAT** (68 s) | every gained instance is R-1 (complete, not sampled) |
| t1_lost_complete | STT_6 + both defenses | facts only: a gen perturbation where old is secure, new is not, and no R-1 witness | no instance in 900 s (timeout) | consistent with the argument below; not a proof |

**Old-vs-new differential.** (1) Uniform sample: the first 3000 instances of each model in production enumeration order (`results/model_fixes_20261108/sample_{STT_6,STT_6_v2}.out`), each evaluated under both semantics by `mf_semantics.py` (useful = `gen_useful_litmus` and `tag_xm`): **STT_6 → v2 lost 0/3000; STT_6_v2 gained 114/3000 (3.8%)**, every one "secure at no_p" under the old fold and every one with an R-1 witness (a non-speculative load and a speculative load of the same word, the speculative one reaching xm). Split: 48 load-xm + 9 load-xm where the non-speculative load has no output; 48 + 9 likewise for br_x transmitters. (2) The Alloy differential samples above: t1_gained 300/300 have the same R-1 witness (`mf_classify.py t1_gained`); t1_lost found nothing. (3) Why everything gained is R-1, and what "lost" would have to be (argument; the completeness queries above check it where they finished). Under every perturbation `gen_useful_litmus` uses (no_p, RR, RC+RR, RS; the flat model has no RO/RI), the old flagged set is a subset of the new one: old seeds are the operands on words no non-speculative load read; a `Store.outmem` seed reaches a transmitter only over rf into a load's `Inmem` of the same word, and that load is then speculative (otherwise the word would have been removed), i.e. a new seed. So new-secure implies old-secure, new minimality implies old minimality, and **gained ⇔ new-useful and the old model does not flag xm at no_p**, which is exactly "xm is reached only from a speculative re-load of a non-speculatively read word" (R-1). **Lost ⇔ some minimality perturbation under which old says secure only because a load it made non-speculative unprotected a word that a still-speculative load reads** (e.g. committing the first unresolved branch makes an older re-load non-speculative). Those old instances claimed a branch or state was necessary only through the location artifact; their minimal versions are new instances.

### B. Recon_6_v2: the ReCon reveal rule (urgent), with A and the rf fact

**What was wrong.** `Recon_6.als:316-318` removes from `Mem_s` every state with an operand that reaches, over `^op_edges`, the address of a non-speculative load. QR2 showed it is a no-op (always equal to STT_6's set, 823 s UNSAT), and even as intended it reveals transitively through ALUs and stores, at LD2 non-speculation, never conceals, and works on locations (audit R-2; `SOURCE_AUDIT_RECON.md` R-SA-10).

**What the paper and the code say (read this session).** Reveal needs a **direct** load pair: "RECON limits its detection to only the leakage of load pairs with a direct dependence" (`aimoniotis-2023-recon.pdf` §4.3), detected "by checking to see if there is a dependence between the destination register of a preceding first load and the source register of a following second load" (§4.3). It happens at **LD2's commit**: "When the second load (LD2) of a load-pair commits, the address accessed by the first load (LD1) is marked as revealed" (§5.2; §4.1 ②; §5.1 "we opt for implementing load-pair detection in the commit stage"). It is **per word** (§5.2 "a bit vector with each cache line to mark the data words"). A store **conceals**: "Once an address is revealed, it is guaranteed to be safe as long as its contents do not change" (§4.4), "upon the commit of a store instruction, the bit of the corresponding word is cleared" (§5.2), and in-flight stores forward concealed data (§4.4.2 ⑧⑨). The reveal only un-taints the re-load: "for STT, any load that receives a revealed value untaints its destination register" (§5.4). gem5-recon (`~/Downloads/dockerrecon/gem5-recon`): the Reveal is sent from `LSQUnit::commitLoad` when LD2's renamed source equals LD1's LPT entry (`src/cpu/o3/lsq_unit.cc:870-918`), LD1's address is recorded at its commit (`:946-956`), a committing non-load that writes the register drops the entry (`src/cpu/o3/commit.cc:1033-1054`), a performed store clears the word's bit (`src/mem/cache/base.cc:1218-1223`), and a returning load with the bit sets `inst->revealBit` (`lsq_unit.cc:183-185`).

**The change, in plain words.** Same skeleton as STT_6_v2 (byte-identical: `diff STT_6_v2.als Recon_6_v2.als` is only the header and the defense block). A speculative load L3's memory read m is **revealed**, and so not a taint source, iff there are loads LD1, LD2 with: LD2 committed; LD1's `Outreg` rf-feeds LD2's `Inaddr` (one rf edge, so no instruction in between); LD1 reads the same word as m and is before L3; and no store writes that word anywhere between LD1 and L3. Everything is perturbation-aware (`i_p`, `o_p`, `rf_p`, `spo_p`, `committed_p`), so RC on LD2 or RI of an in-between ALU change the reveal the way they would in the perturbed program.

```diff
--- a/STAGE1_alloy/models/Recon_6.als
+++ b/STAGE1_alloy/models/proposed/Recon_6_v2.als
@@ -1,3 +1,18 @@
+// =============================================================================
+// Recon_6_v2.als — DRAFT, NOT APPROVED (2026-11-08, session model-fixes).
+// Derived from Recon_6.als (sha256 01252c82c6c0b75522e7c465b92b1c7e9631c94a9bd7a9fa6d7d7b8fc5ab8247), which is unchanged.
+// Skeleton = STT_6_v2.als byte for byte; `diff STT_6_v2.als Recon_6_v2.als` is this
+// header plus the ReCon defense block. Changes vs Recon_6.als, each marked:
+//   [v2-1] fact rf_from_most_recent_writer, verbatim from STT_6.als:161-169 (audit R-3:
+//          25.8% of Recon_6 instances read a register past a newer writer).
+//   [v2-2] instance-based protection set (as STT_6_v2.als).
+//   [v2-3] ReCon reveal rewritten: direct load pair (LD1.outreg -rf-> LD2.inaddr, no
+//          instruction between), only once LD2 COMMITS, per word (Mem_s), concealed by any
+//          store to the word between LD1 and the re-load; the reveal un-protects only the
+//          re-load's memory read (ReCon §4.1, §4.3, §4.4, §5.1, §5.2, §5.4; gem5-recon
+//          lsq_unit.cc:870-956, commit.cc:1033-1054, base.cc:1218-1223). Fixes R-1/R-2.
+// Review + evidence: wiki/state/ALLOY_MODEL_CHANGES.md "2026-11-08 — model-fixes".
+// =============================================================================
 
 
 /*********************************************************************************
@@ -157,6 +172,16 @@
 fact one_entering_rf {all o: Operand | lone rf.o}
 fact unidirectional_rf {acyclic[(operands).rf.(~operands) + spo]}
 fact same_state_rf {no ((~opstate).rf.opstate - iden)}
+
+// [Option A] rf must read from the MOST-RECENT writer of the state:
+// forbid another writer of the same state spo-between an rf producer and its use.
+fact rf_from_most_recent_writer {
+  all prod: Instruction.outs, use: prod.rf |
+    no other: (Instruction.outs - prod) |
+        other.opstate = prod.opstate
+        and (prod.(~operands))  -> (other.(~operands)) in ^spo
+        and (other.(~operands)) -> (use.(~operands))   in ^spo
+}
 
 fact ld_ddi    {no (Loads.operands <: ddi) - (Inmem->Outreg)}
 fact str_ddi   {no (Stores.operands <: ddi) - (Inreg->Outmem)}
@@ -218,15 +243,15 @@
 
 fun speculative_xmit_p[p: PTag->univ] : Operand {leakage_function_p[p] <: speculation_contract_p[p].operands}
 
-fun a[p:PTag->univ,i:Instruction,s:State] : State { prot_set_propagation_p[p,i,s]}
-fun last_committed_protset_p[p: PTag->univ] : State {
+fun a[p:PTag->univ,i:Instruction,o:Operand] : Operand { prot_set_propagation_p[p,i,o]} // [v2-2] Operand-typed protection set
+fun last_committed_protset_p[p: PTag->univ] : Operand { // [v2-2]
 		a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
 a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
 a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]).(spo_p[p]),
 a[p,f[p].(spo_p[p]).(spo_p[p]).(spo_p[p]),
 a[p,f[p].(spo_p[p]).(spo_p[p]),
 			a[p,f[p].(spo_p[p]),
-				a[p,f[p],hardware_protection_policy[p]]
+				a[p,f[p],hardware_protection_policy[p]] // [v2-2]
 			]
 	]
 ]]]]
@@ -250,16 +275,18 @@
 }
 
 pred secure_speculation_scheme_p[p: PTag->univ] {
-	(no (last_committed_protset_p[p].(~opstate) & speculative_xmit_p[p])) and
-	(no last_committed_protset_p[p].(~opstate).(^(op_edges_p[p])) & speculative_xmit_p[p])
+	// [v2-2] the protection set is a set of operands now, so no .(~opstate) lift (same form as SPT_6_oneLP_v2.als:287-296)
+	(no (last_committed_protset_p[p] & speculative_xmit_p[p])) and
+	(no last_committed_protset_p[p].(^(op_edges_p[p])) & speculative_xmit_p[p])
 }
 
 // make sure there is some overlap in the end btw xm and speculative xmit
 //fact tag_xm {some xm & speculative_xmit_p[xm]}
 fact one_xm {#(xm) = 1}
 fact tag_xm { 
-	(some (last_committed_protset_p[no_p].(~opstate) & speculative_xmit_p[no_p] & xm.operands)) or
-	(some last_committed_protset_p[no_p].(~opstate).(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands)
+	// [v2-2] Operand-typed, as in secure_speculation_scheme_p
+	(some (last_committed_protset_p[no_p] & speculative_xmit_p[no_p] & xm.operands)) or
+	(some last_committed_protset_p[no_p].(^(op_edges_p[no_p])) & speculative_xmit_p[no_p] & xm.operands)
 }
 
 /*********************************************************************************
@@ -313,13 +340,44 @@
 
 //fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & (no_unresolved_brs_p[p] + no_unresolved_mem_p[p])}
 fun speculation_contract_p[p: PTag->univ] : Instruction {uncommitted_p[p] & has_unresolved_brs_p[p]}
-fun hardware_protection_policy[p: PTag->univ]: State {Mem_s - 
-(~opstate).(^(op_edges_p[p]).(~inaddr).(Loads-speculation_contract_p[p])) // speculative loads backwards through dd to state
-} // 
+//fun hardware_protection_policy: State {Mem_s}
+// [v2-3] ReCon reveal / conceal, per word (Mem_s) and per re-load instance. The memory read m of a
+// load L3 is REVEALED iff some direct load pair LD1 -> LD2 has exposed m's word:
+//   - LD1 reads the same word, and LD1 is spo-before L3;
+//   - LD1's output register is LD2's address register over ONE rf edge, i.e. no instruction in
+//     between (ReCon §4.3 "RECON limits its detection to only the leakage of load pairs with a
+//     direct dependence"; gem5 lsq_unit.cc:872-880 matches LD2's renamed source to LD1's dest, and
+//     commit.cc:1046-1054 drops the entry when any other instruction writes that register);
+//   - LD2 has COMMITTED (§4.1 (2), §5.1 "detection in the commit stage", §5.2 "When the second load
+//     (LD2) of a load-pair commits, the address accessed by the first load (LD1) is marked as
+//     revealed"; gem5 sends the Reveal from LSQUnit::commitLoad, lsq_unit.cc:870-918);
+//   - no store writes the word spo-between LD1 and L3 (conceal: §4.4 "Once an address is revealed,
+//     it is guaranteed to be safe as long as its contents do not change", §4.4.1 / §5.2 a committed
+//     store clears the word's bit, gem5 base.cc:1218-1223; §4.4.2 a younger in-flight store forwards
+//     concealed data). A store between LD1 and LD2 also conceals here: LD2 leaked the OLD value
+//     (paper §4.4); gem5 re-reveals in that case (SOURCE_AUDIT_RECON.md R-SA-2), so such a test is
+//     a leak in the model and exposes R-SA-2 when the reveal works.
+// A revealed read is not a taint source (§5.4 "for STT, any load that receives a revealed value
+// untaints its destination register"); everything else is exactly STT_6_v2.
+fun revealed_p[p: PTag->univ] : Operand {
+	{ m: Loads.inmem & o_p[p] | some ld1, ld2: Loads & i_p[p] |
+		ld2 in committed_p[p]
+		and some (ld1.outreg.(rf_p[p]) & ld2.inaddr)
+		and m.opstate in (ld1.inmem & o_p[p]).opstate
+		and ld1 -> m.(~inmem) in ^(spo_p[p])
+		and (no s: Stores & i_p[p] | m.opstate in (s.outmem & o_p[p]).opstate
+			and ld1 -> s in ^(spo_p[p]) and s -> m.(~inmem) in ^(spo_p[p])) }
+}
+// [v2-2] instance-based protection (as STT_6_v2.als) minus the revealed reads [v2-3]
+fun hardware_protection_policy[p: PTag->univ]: Operand {((Loads & speculation_contract_p[p]).inmem & o_p[p]) - revealed_p[p]}
+// old (Recon_6.als:316-318), a no-op (audit QR2): Mem_s - (~opstate).(^(op_edges_p[p]).(~inaddr).(Loads-speculation_contract_p[p]))
 // fun leakage_function : Operand {Loads.inaddr+(Branchxs+Otherxs).inreg}
 fun leakage_function : Operand {Loads.inaddr+(Branchxs).inreg}
-fun prot_set_propagation_p[p:PTag->univ,i:Instruction,s:State] : State {
-	// s - (Loads & committed_p[p] & i).inaddr.opstate // committed loads remove their inaddr from the protset
-	s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate // loads that have no unresolvd brs before them remove their inaddr from protset (acc load is not branch so probs chill)
+fun prot_set_propagation_p[p:PTag->univ,i:Instruction,o:Operand] : Operand {
+	// [v2-2] nothing is ever de-protected in program order: the seed is already the final set
+	// (old, location-based: s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate, i.e. any
+	//  non-speculative load made its whole LOCATION public, so a later speculative re-load of the same
+	//  word was never a leak; audit R-1 / QR1a, STT-3 / Recon F2)
+	o
 }
 
```

**Validation (Alloy, `exactly 6`, facts only unless noted; every witness re-checked by `mf_semantics.py`).**

| Query | Asks | Recon_6_v2 | Control |
|---|---|---|---|
| (a) `t2a_recon` | committed direct pair LD1→LD2 on word A; speculative re-load of A feeds a load xm; no store to A between | **UNSAT** (1 s): not flagged | STT_6_v2: SAT (1 s); with gen SAT: `r0 <- [M0]` (C) ; `ld [r0]` (C) ; br (U) ; `r0 <- [M0]` ; `ld [r0]` = xm ; `st r0 -> [M0]`, the exact ReCon pattern |
| (b) `t2b_recon_any` | as (a) with a store to A between LD1 and the re-load | **SAT** (0 s): flagged | — |
| (b1) `t2b1` | that store committed after LD2 (paper §4.4.1 conceal) | SAT (1 s) | — |
| (b2) `t2b2` | that store not committed (forwards concealed data, §4.4.2) | SAT (1 s) | — |
| (b3) `t2b3` | that store between LD1 and LD2 (gem5 re-reveals: R-SA-2 stale reveal) | SAT (0 s) | — |
| (b) with gen | | SAT (2 s): LD1 ; LD2 ; committed `st -> [M0]` ; br (U) ; re-load ; xm | — |
| (c) `t2c_recon` | LD1 → ALU → LD2 committed, re-load feeds xm, no store | **SAT** (1 s): flagged, no reveal; with gen SAT (1 s) | — |
| (d1) `t2d1` | Recon's protection set differs from STT_6_v2's at no_p (the QR2 analogue) | **SAT** (3 s); QR2 on Recon_6 was UNSAT (823 s) | — |
| (d2) `t2d2_recon_only` | Recon_6_v2-useful and not STT_6_v2-useful (gen) | **300 (cap, 133 s)** | all 300: LD2 is the first uncommitted instruction, so the boundary perturbation RC+RR commits it and the reveal makes the leak go away; e.g. `r0 <- [M0]` (C) ; `ld [r0]` (uncommitted) ; br (U) ; `r0 <- [M0]` ; `br_x r0` = xm |
| (d3) `t2d3_stt_only` | STT_6_v2-useful and not Recon_6_v2-useful (gen) | **300 (cap, 27 s)** | all 300: a revealed re-load is the only path to xm at no_p (the (a) shape) |
| cores | `Recon_6_v2_core_ri` vs `STT_6_v2_core_ri` | 129 / 129 at `but 3`, 129 / 129 at `but 4` (exhaustive; the old STT_6/Recon_6 RI cores were also 129) | Recon-core-and-not-STT-core: **UNSAT** at `but 5` (340 s); STT-core-and-not-Recon-core: **UNSAT** at `but 5` (67 s); "some committed load in a Recon core": **UNSAT** at `but 5` (203 s) |

**So is R-1 resolved?** In the flat model, yes: Recon_6_v2 and STT_6_v2 now generate different instances in both directions (d2, d3), and ReCon's three rules (direct pair, commit, conceal) each have a SAT witness that the defense must block (b, c, d2) and an UNSAT case where it may let the transmitter go (a). **At Stage 1 (RI-only cores), no, and it cannot be: a reveal only ever removes a leak, so the LD1/LD2 pair is never RI-necessary, no RI core contains a committed load (UNSAT above), and the Recon and STT RI core sets are identical** (both directions UNSAT at `but 5`). The ReCon difference therefore appears only in Stage 1.5, where the flat `Recon_6_v2.als` grows each core and its RR/RC/RS minimality keeps the (b)/(c)/(d2) shapes (register reuse lets the pair's register be RS-necessary, as in every witness above). If Stage 1 must contain ReCon-specific cores, the Recon core needs a different minimality (DECIDE B2).

**Old Recon_6 → Recon_6_v2, in total.** = (rf fact) + (A) + (reveal). Sample of the first 3000 Recon_6 instances: 775 (25.8%, as the audit measured) read past a newer writer and are removed by the rf fact; the other 2225 stay useful under Recon_6_v2 (0 lost to A or the reveal). Sample of the first 3000 Recon_6_v2 instances: 116 (3.9%) are new, all R-1 (none of the first 3000 involves a reveal; the reveal shapes need register reuse and come later in the enumeration, d2/d3).

**What test actually exercises the reveal in gem5 (for the ReCon run, E6).** Stage 2 emits a load with a specified address as `movq (%probe_base, %rN, 1)` (`STAGE2_compilation/parsexml.py:2505-2521`), so LD2 = `ld [r0]` really is a direct pair with LD1's destination as the index register, and the re-load of `Mem_s0` is a `mem_base` slot read, the same word LD1 read. Two conditions are not in the model and must come from Stage 2 or the harness: (1) the re-load must reach the cache **after LD2 commits** (recon-ruby measured the speculative load and transmitter at tick 3040000 vs LD2 retiring at 3042000, so in a one-pass litmus the reveal is always too late; `wiki/state/EVAL_MANIFEST.md` "Does the reveal fire?"), e.g. a serializing instruction after the committed prefix or a delayed window start; (2) the build must deliver the reveal (Ruby; classic caches send it to paddr 0, R-SA-1). With both, the generated tests split as: (b)/(c)/(b3) shapes must still be blocked (a hit there is a ReCon bug: conceal missing, ALU pair accepted, or R-SA-2 stale reveal); the d2 shape (LD2 still in flight) must be blocked by a commit-time reveal; the (a) shape is not generated (allowed). Today 0 of 150,000 Recon_6 tests have a speculative load of a revealed word (claudelog 2026-11-08 21:30); under Recon_6_v2 the d2/d3 differentials show such shapes exist in large numbers.

### C. `rf_from_most_recent_writer` in every in-use model (prepared, NOT applied)

**Status.** The fact is in STT_6, every STT_6 variant, STT_6_stl and SPT v2 (and therefore in A, B, D). It is missing from the 7 in-use files below. Patched copies (fact inserted verbatim from `STT_6.als:161-169` right after `fact same_state_rf`, the same place as in STT_6) are in `results/model_fixes_20261108/rf_patched/` with one `.diff` each and `HASHES.txt`. **To apply (Anna):** `bash STAGE3_gem5/triage/model_audit_20261108/apply_rf_fact.sh` (refuses any file whose current hash is not the recorded old hash; checks the new hash).

| File | sha256 old → new | hunk | `gen_lit` check on the patched copy |
|---|---|---|---|
| `Recon_6.als` | 01252c82c6c0 → 6f30619586f1 | `@@ -157,6 +157,16 @@` | SAT (3 s) |
| `proposed_twophase/Recon_6_core.als` | dfb81a8002c9 → 05178cf057c2 | `@@ -161,6 +161,16 @@` | SAT (limit 1, 15 s); unpatched control SAT (9 s); the earlier limit-3 run timed out at 600 s because this RO+RI core has only ~2 instances in total |
| `proposed_twophase/Recon_6_core_ri.als` | a3e691eb324f → 40c4bd9494e7 | `@@ -161,6 +161,16 @@` | SAT (6 s) |
| `proposed/Recon_6_stl.als` | e87c2124c479 → 9b397f5d5561 | `@@ -166,6 +166,16 @@` | SAT (3 s) |
| `proposed_twophase/Recon_6_stl_core.als` | aeabedb829ce → 1b1c78de4369 | `@@ -170,6 +170,16 @@` | SAT (2 s) |
| `proposed/SPT_6_oneLP_stl.als` | b501c758cabe → 8e37b2265c0e | `@@ -166,6 +166,16 @@` | no instance in 600 s; the unpatched file already generates 0 (RS vs alias conflict, EVAL_MANIFEST.md:237) |
| `proposed_twophase/SPT_6_oneLP_stl_core_conservative.als` | 8f7773b41c08 → 8bdf742eab8d | `@@ -171,6 +171,16 @@` | stopped (same known-0 model); parses |

Every diff is the same 10 added lines; the Recon_6 one, exactly:

```diff
--- a/STAGE1_alloy/models/Recon_6.als
+++ b/STAGE1_alloy/models/Recon_6.als
@@ -157,6 +157,16 @@
 fact one_entering_rf {all o: Operand | lone rf.o}
 fact unidirectional_rf {acyclic[(operands).rf.(~operands) + spo]}
 fact same_state_rf {no ((~opstate).rf.opstate - iden)}
+
+// [Option A] rf must read from the MOST-RECENT writer of the state:
+// forbid another writer of the same state spo-between an rf producer and its use.
+fact rf_from_most_recent_writer {
+  all prod: Instruction.outs, use: prod.rf |
+    no other: (Instruction.outs - prod) |
+        other.opstate = prod.opstate
+        and (prod.(~operands))  -> (other.(~operands)) in ^spo
+        and (other.(~operands)) -> (use.(~operands))   in ^spo
+}
 
 fact ld_ddi    {no (Loads.operands <: ddi) - (Inmem->Outreg)}
 fact str_ddi   {no (Stores.operands <: ddi) - (Inreg->Outmem)}
```

**Consequences.** Testsets generated from the old hashes predate the fact: `testsets_latest/Recon_6` (Recon_6 sha256 01252c82, 25.8% stale rf in a 3000 sample, 50/3000 programs whose transmitter reads a constant-derived value per the audit). simspect-c8's running Recon Stage 1 on cafe2 (`/tests/simspect_alloy_20261108`) uses the old `Recon_6_core_ri.als` (a3e691eb…); not touched. Whether the fact changes the Recon RI core set was not measured with the old Recon core; STT_6_core_ri (which has the fact) and Recon_6_v2_core_ri both give 129 at `but 3`, like the old Recon_6_core_ri.

**STL drafts, one semantic note.** In `Recon_6_stl.als` / `SPT_6_oneLP_stl.als` the true alias is atom-based (`stl_alias_atom`) and "rf not required (the bypassing load reads the stale value, not the store's)". With the fact, the bypassing load can still have no rf edge, or an rf edge from the unresolved store itself, but it can no longer have an rf edge from an *older* writer of the word past that store (the stale-value flow of a bypass). That matches the approved `STT_6_stl.als`, which already has the fact; under the instance-based seed (A) the bypassing load's read is protected anyway, so no taint path depends on that edge.

**Legacy, leave alone (or archive):** `SPT_6_oneLP.als`, `SPT_6_oneLP_noSTLF.als`, `proposed_twophase/SPT_6_oneLP_core.als`, `proposed_twophase/SPT_6_oneLP_core_conservative.als` (pre-v2 SPT, provenance only, superseded by v2), `SPT_6.als` and its symlink `SPT_6_full.als`, `STT_2.als`, `STT_3.als`, `STT_4.als`, `STT_4_new.als`, `STT_5.als`, `STT_5_ld_xmit_only.als`, `LP-only-STT_3.als` (STT development history), `STT_6_modified_protset.als`, `STT_6_pincommit.als` (contract experiments, never enumerated). Note: `STAGE1_alloy/models/MANIFEST.md` says the last two "add `rf_from_most_recent_writer`"; neither file contains it (grep), so that MANIFEST row is wrong.

### D. SPT_6_oneLP_v3: audit S-1, Option A (approved by Anna for now)

**What was wrong.** v2-4 declassifies only the transmitted value and its rf producer, so the producer load's `Inmem` stays protected and the transitive `^op_edges` term re-flags every other reader of the declassified value (audit S-1: Q1 SAT on v2, UNSAT on pre-v2). Paper: "the operands of transmitters/branches are untainted when the instruction becomes non-speculative" (`choudhary-2021-spt.pdf` p612 §6.3, as the audit cites); gem5-spt untaints the committed load's address register (`lsq_unit_impl.hh:1189-1209`, per the audit).

**The change, in plain words.** One line in defense clause 2: when a non-speculative transmitter declassifies a value, also remove the memory read of the load that produced it (one ddi hop back from the declassified `Outreg`), and nothing further back.

```diff
--- a/STAGE1_alloy/models/SPT_6_oneLP_v2.als
+++ b/STAGE1_alloy/models/proposed/SPT_6_oneLP_v3.als
@@ -1,4 +1,10 @@
 // =============================================================================
+// SPT_6_oneLP_v3.als — DRAFT, NOT APPROVED (2026-11-08, session model-fixes).
+// = SPT_6_oneLP_v2.als (sha256 acb1f2e21e5e6c3b98e7dfd8eec71bc9d9282578303626655334768addb61e8d, unchanged) plus ONE change:
+//   [v3-1] declassification also removes the producer load's Inmem (audit S-1, Option A,
+//          wiki/findings/audits/2026-11-08/MODEL_AUDIT_SPT_RECON.md). Review: wiki/state/
+//          ALLOY_MODEL_CHANGES.md "2026-11-08 — model-fixes". The v2 header below is kept as is.
+// =============================================================================
 // SPT_6_oneLP_v2.als — consolidated SPT model for the final batch (2026-11-08,
 // resolve-hooks session, at Anna's request). DRAFT until Anna signs off.
 // Derived from SPT_6_oneLP.als (sha256 713d0904d91aa9cb5a25a33c1e60ae1156a38caea0d9c1173d4a7959aa898809), which is kept unchanged.
@@ -381,7 +387,10 @@
 	o // - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem // loads that have no unresolvd brs before them remove their inaddr from protset (acc load is not branch so probs chill)
 	// subtract the operands that leak 
 	// - (i.operands & nonspeculative_xmit_p[p]).*(~(op_edges_p[p]))
-	- (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p])) // [v2-4] the transmitted value and its producer only
+	// - (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p])) // [v2-4] the transmitted value and its producer only
+	// [v3-1] also declassify the producer LOAD's memory read (one ddi hop back from the declassified Outreg),
+	// so the transitive ^op_edges term no longer re-flags the declassified value's other readers (audit S-1, Option A)
+	- (let d = (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p])) | d + (d & Loads.outreg).(~(ddi_p[p])))
 	// subtract outreg if inreg taintd
        - (i & ((Otherns + Otherxs) - inreg.Inreg)).outreg
 	// when every input is outside of prot set untaint output
```

**Validation.**

| Query | Result | Meaning |
|---|---|---|
| Q1 on v2 (with gen) | SAT (7 s) | reproduces the audit |
| Q1 on v3 (with gen) | **SAT (11 s)** | witness: `st -> [M0]` (C, no data register) ; `r0 <- [M0]` (C, rf from the store) ; `ld [r0]` (C) ; br (U) ; `ld [r0]` = xm. The store's `Outmem` is still seeded and reaches the declassified load's `Inmem` over rf, so the transitive term re-flags |
| Q1 on v3 plus "no rf into the producer's `Inmem`" | **UNSAT (10 s)** | Option A fixes every S-1 case where the declassified load reads memory directly |
| `t4_lost` = v2-useful, not v3-useful, realisable (a memory-reading load in xm's backward cone) | 300 (cap, 32 s) | all 300 have a load whose value reaches a non-speculative transmitter (the S-1 shape), none has a store→load rf; e.g. `r0 <- [M0]` (C) ; `br_x r0` (U, the non-speculative transmitter) ; `br_x r0` = xm |
| `t4_gained` = v3-useful, not v2-useful | 0 found in 1801 s (timeout) | v3 flags ⊆ v2 flags (the fold is antitone in what is removed), so gains can only come from easier minimality; none found |
| `t4_lost_complete` = realisable, v3 does not flag xm, and no load value reaches a non-speculative transmitter (facts only, on v2) | no instance in 900 s (timeout) | consistent with "v3 only un-flags S-1 shapes"; not a proof |
| RI cores at `but 3`: v2 / v3 | 546 / **393** (50 s / 53 s, exhaustive) | the v2 set splits 153 with "a load value transmitted non-speculatively" + 393 without; v3 has 393, all without (count match, not a proven set equality) |
| v2 3000-instance sample | 3/3000 have the S-1 shape, all with the load reading memory directly (none store-forwarded) | v3 removes all three |

**Residual and Option B.** v3 still flags the declassified value when the producer load's `Inmem` is rf-fed by a store (the Q1 v3 witness). That is over-strict (O, a false positive), never unsound, and 0/3000 in the v2 sample. One note on the lost set: when the non-speculative transmitter is a `br_x`, gem5-spt does not declassify branch predicates (SOURCE_AUDIT_SPT B1), so gem5 would still protect those xm; dropping them from the corpus loses no gem5 leak, it only stops scoring a paper-allowed case. **Option B (described, not applied):** drop the `^(op_edges_p[p])` term from `secure_speculation_scheme_p` and `tag_xm` (flag only operands in the final protection set), and make the fold compute forward taint explicitly: at each step add `i`'s outputs whose inputs are in the set (`(i & (Otherns+Otherxs) & inreg.o).outreg`, a load's `Outreg` when its `Inmem` or the forwarding store's data is in the set, a store's `Outmem` when its data `Inreg` is in the set, an rf consumer `(i.ins & o.(rf_p[p]))`), apply the existing untaint rules after that (which also fixes the P3 one-step lag), and declassify only the transmitted value (v2-4) without the extra Inmem hop. Because a declassified register would then never be re-added from older memory, the store-forwarded residual goes away and SPT's backward rules become the only untaint path, as in the paper (§6.3-§6.7). It is a rewrite of clause 2 and of two skeleton predicates, so it needs its own validation: Q1 UNSAT, the v2 differential, and the STL rule (S-3) re-checked, because the transitive term currently hides the missing STLPublic gate.

**Is the running SPT Stage 1 / 1.5 affected?** Yes, by construction, if it uses `SPT_6_oneLP_v2_core_ri.als` / `SPT_6_oneLP_v2.als`: 153 of the 546 cores at size 3 are S-1 cores that v3 drops, and every Stage-1.5 instance grown from v2 can contain the S-1 false positive. Not checked on cafe2 (read-only check: `python3 STAGE1_alloy/models/proposed_twophase/stage1_status.py` and `status/stage15_status.json` in `/tests/simspect_alloy_20261108`). If Anna adopts v3, SPT Stage 1 and 1.5 need re-running from `SPT_6_oneLP_v3_core_ri.als`.

### Queries, scripts, reproduction

- Query copies: `STAGE3_gem5/triage/model_audit_20261108/queries/mf/<name>.als` built by `mk_mf_queries.py` (lists `RUNLIST.tsv`, `RUNLIST2.tsv`, `RUNLIST3.tsv`, `RUNLIST4.tsv`); auxiliary definitions `aux_stt_old.alsfrag`, `aux_stt_new.alsfrag`, `aux_r1w.alsfrag`. Runner: `runq_mf.sh <query.als> <limit> <timeout>` (waits for a free Java slot, Java 17, `a6CountModels`, `-Xmx6g`) and `run_mf_list2.sh <RUNLIST>`. Every run is a line in `queries/model_fixes_runs.log` (start, query, limit, rc, seconds, "Total models"; rc 124 = timeout; "Total models: 0" with rc 0 = exhausted, UNSAT at that scope). Outputs (XML/txt witnesses) sit next to each query as `<name>.out/`.
- Semantics cross-check: `mf_semantics.py <dir>` (STT_6, Recon_6, STT_6_v2, Recon_6_v2 at no_p and every flat perturbation, plus the stale-rf count) and `mf_classify.py <query>` (explains every instance a differential returned).
- Large samples (gitignored): `results/model_fixes_20261108/sample_{STT_6,Recon_6,STT_6_v2,Recon_6_v2}.{als,out,json}`; rf patches `results/model_fixes_20261108/rf_patched/`.
- Not run (Java budget, one slot): exhaustive counts of the differentials (all capped at 300 or stopped by the timeout).

### Decisions for Anna (also in `URGENT_TODO.md` "Manual source audit")

- **A1. Approve diff A (STT_6_v2)?** It changes four shared skeleton lines (State → Operand), not only the defense block, which is the only way to express per-instance protection; the Operand skeleton is the one SPT v2 already uses. Recommendation: approve, and use STT_6_v2 for the two-stage regen.
- **B1. Reveal at LD2's commit (as given, = gem5) or at LD2's visibility point (the paper's security bound, §5.1: "the earliest that LD2 becomes non-speculative is when the load has reached its visibility point ... implementing load-pair detection in the commit stage ... has no impact on security")?** With commit, the 300+ d2 instances (LD2 non-speculative but in flight) are leaks; a build that reveals at the VP would hit them without a security bug. Recommendation: commit (matches the code; over-generates, which is the direction you asked for); label d2 hits "early reveal" in triage.
- **B2. Stage 1 for ReCon:** the Recon and STT RI cores are provably the same set (reveals never make an instruction necessary). Options: (a) keep RI cores and let Stage 1.5 (flat Recon_6_v2) produce the ReCon shapes; (b) a Recon core minimality that ignores the reveal pair (e.g. RI over non-pair instructions only) to get ReCon-specific cores; (c) a forced ReCon seed (committed direct pair + re-load) in Stage 1.5. Recommendation: (a) now plus (c) for the ReCon run, since the shapes are cheap to force.
- **B3. Stale reveal (R-SA-2):** the model conceals when a store hits the word between LD1 and LD2 (paper §4.4), so b3 tests are leaks and expose R-SA-2 once the reveal works. Recommendation: keep (paper semantics).
- **B4. A Stage-2/harness knob so the speculative re-load issues after LD2 commits** (serialize after the committed prefix), without which no ReCon test can observe a reveal. Recommendation: yes, for the E6 ReCon row only.
- **C1. Apply the rf fact** with `apply_rf_fact.sh` (prepared, hash-checked). The two STL SPT files generate 0 with or without it (known RS-vs-alias conflict), so the check there is only that they parse.
- **D1. SPT residual:** accept v3's store-forwarded false positive (0/3000 in the sample) and schedule Option B later, or do Option B before the SPT regen. Recommendation: accept now, Option B with the next SPT round.

---

## 2026-11-08 — STT_6_s4 / STT_6_a3c: make the S4 and A3c shapes generable (DRAFTS, unapproved; s4-variant)

**Bottom line.** STT_6 provably cannot emit either shape (forced queries return 0 instances). Each new draft adds one scoped minimality exemption and changes nothing else; both shapes then exist in large numbers (more than 20,000 each, capped). Stage 2 concretizes both cleanly (100/100 annotations resolve per draft), but **S4 still cannot fire in gem5: Stage 2 replaces every non-transmitter branch's condition with an immediate** (`STAGE2_compilation/parsexml.py:2846-2866`). So B1's predicate never reads L1, and B1 is never tainted (100/100 sampled tests). A3c's taint chain does survive (B1 is the transmitter branch, `br_bez` reads L1, 100/100), but lining up the same-cycle resolution needs a per-branch stall knob that the pipeline doesn't have, and there is no detector. **No gem5 run was done:** neither sample can exercise its mechanism yet, so a run would only produce misleading zeros. The STT_6.als contract and skeleton are untouched in both drafts.

**Files (all new):** `STAGE1_alloy/models/proposed/STT_6_s4.als`, `STAGE1_alloy/models/proposed/STT_6_a3c.als`, `STAGE1_alloy/models/proposed/STT_6_s4_queries.py` (regenerates every query below), `testsets/STT_6_s4_draft/` and `testsets/STT_6_a3c_draft/` (50 XML each plus llvm/asm/ann, both modes), `runconfigs/fixed_20261030/STT_6_{s4,a3c}_draft_stt.jsonc` (E3's `STT_6_stt_fixed_latest.jsonc` with only `testset_dir`/`results_name` changed). On cafe2: `/tests/simspect_fixed_20261030/testsets_s4_draft/` and the same two runconfigs (`testset_dir: testsets_s4_draft`). No results dirs exist.

### Why STT_6 can't emit them (the real cause is minimality, not the contract)

- **S4 shape** (`SOURCE_AUDIT_STT.md` S4): B0, an older branch that is correctly predicted but slow; L1, a load after B0; B1, a branch whose predicate comes from L1 and which mispredicts; then L2 → T on B1's wrong path. Under Anna's rule (2026-11-08: executed but not yet squashed = unresolved), the contract snapshot at the leak is B0 resolved and B1 unresolved. That is already an STT_6 violation: L2 runs after an unresolved branch, so T's address is protected. What STT_6 drops is the **context**. B0 is the oldest uncommitted instruction and is resolved, so the boundary clause `secure[RC->first_uncommitted + RR->first_uncommitted]` (`STT_6.als:308`) fails: committing B0 changes nothing, and the instance is pruned. Query q0 (STT_6 minimality plus the forced shape) = **0**.
- **Why that context matters (paper + code):** STT §6.4.1 p7 (`~/Documents/quail/sources/papers/yu-2019-stt.pdf`): "Resolution-based channels are eliminated by delaying the effects of branch resolution until the branch's predicate becomes untainted." `/work/stt` implements the delay as a *pending squash* when `isArgsTainted()` (`commit_impl.hh:936-952`), and fires it from `getResolvedPendingSquashInst` only in a later commit cycle (`:964-969`). Whether B1's predicate is tainted, and which older branch keeps it tainted, therefore decides *when* B1's squash happens. The contract's minimality treats that context as irrelevant because the contract verdict doesn't change.
- **A3c shape** (`wiki/findings/bug/BUG_TAXONOMY.md` A3c): an older unresolved branch B0; L1; B1 = the transmitter branch, with a predicate from L1 (protected) that mispredicts; B2 = a younger branch with an untainted predicate that also mispredicts. B1's protected predicate inside B0's window is the ordinary STT_6 `br_x` leak. STT_6 drops B2 through resolution-minimality (`STT_6.als:306`): resolving B2 doesn't change the verdict. q8 (STT_6 plus the forced A3c shape) = **0**. Paper basis for B2 mattering: §6.4.1 p7, "it is safe to resolve a branch as soon as its predicate becomes untainted, even if an older branch with a tainted predicate has not yet resolved". A3c breaks exactly that: B2 can't resolve while the older tainted B1 hides it.

### The diffs (everything else is STT_6.als verbatim; the first run command is the new one, and the original `gen_lit` is kept below it)

`STT_6_s4.als` (inserted above `run gen_lit`):

```alloy
fun s4_pred_feed : Instruction -> Instruction {   // L1 -> B1: uncommitted load's outreg rf-feeds an unresolved branch's inreg
	(Loads & uncommitted) <: (outreg.rf.(~inreg)) :> (unresolved & (Branchns+Branchxs))
}
fun s4_l1 : Instruction { s4_pred_feed.Instruction }
fun s4_b0 : Instruction { (Branchns+Branchxs) & resolved & uncommitted & (^spo).s4_l1 }  // older resolved, uncommitted branch
let gen_useful_litmus_s4 {
  not secure_speculation_scheme_p[no_p]
  all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]
  (first_uncommitted in s4_b0) or secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]   // <- the ONLY change
  all s: State | secure_speculation_scheme_p[RS->s]
}
pred s4_shape { some b0: s4_b0, l1: s4_l1, b1: (Branchns+Branchxs) & unresolved, l2: Loads & uncommitted, t: Loads & xm |
    l1 in b0.^spo and (l1 -> b1) in s4_pred_feed and l2 in b1.^spo and t in l2.^spo and some (t.inaddr & l2.outreg.^(rf + ddi)) }
run gen_lit_s4 { gen_useful_litmus_s4 } for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool
run s4_forced  { gen_useful_litmus_s4  s4_shape } for <same scope>
```

`STT_6_a3c.als` (inserted above `run gen_lit`):

```alloy
fun a3c_prot_ops : Operand {   // the two protected-operand terms of secure_speculation_scheme_p
	last_committed_protset_p[no_p].(~opstate) + last_committed_protset_p[no_p].(~opstate).(^(op_edges_p[no_p])) }
fun a3c_witness : Instruction {   // B2: unresolved branch younger than the xmit branch, predicate NOT protected
	(Branchns+Branchxs) & unresolved & (xm & Branchxs).^spo - (inreg.a3c_prot_ops) }
let gen_useful_litmus_a3c {
  not secure_speculation_scheme_p[no_p]
  all i: (unresolved - first_uncommitted - a3c_witness) | secure_speculation_scheme_p[RR->i]   // <- the ONLY change
  secure_speculation_scheme_p[RC->first_uncommitted + RR->first_uncommitted]
  all s: State | secure_speculation_scheme_p[RS->s]
}
pred a3c_shape { some b0: (Branchns+Branchxs) & unresolved, l1: Loads, b1: xm & Branchxs, b2: a3c_witness |
    l1 in b0.^spo and b1 in l1.^spo and b2 in b1.^spo and some (b1.inreg & l1.outreg.^(rf + ddi)) }
run gen_lit_a3c { gen_useful_litmus_a3c } for <same scope>
run a3c_forced  { gen_useful_litmus_a3c  a3c_shape } for <same scope>
```

- **Soundness argument:** both changes only *weaken* one minimality clause, so every STT_6 instance is still an instance of the draft (the drafts are supersets). Each added instance still violates the unchanged contract (`not secure_speculation_scheme_p[no_p]` is kept), and every other element is still minimal. The exemptions admit only the context each mechanism needs: one resolved, uncommitted, older branch (S4), or unprotected younger mispredicted branches after a transmitter branch (A3c).
- **Looseness to know about:** (1) `gen_lit_s4` without the forcing predicate also admits a "branch-transmitter S4" (T is a `Branchx` instead of a load; q7 sample: 50/50 were this, both with and without the dropped RS exemption). It is harmless but not a cache leak on STT; `s4_forced` restricts T to a load. (2) The A3c exemption admits any number of witnesses (up to scope).
- **First draft had a second exemption, now removed:** an RS exemption for L1's output state. It turned out unnecessary. With the boundary exemption alone the forced shape is SAT (q4 ≥ 20,000); with the RS exemption alone it is 0 (q5). RS minimality is satisfied when L1's output register is the same state as the leak path's register, which concretizes to one physical register (every sampled test: `locked_registers` has one `Reg_s` for L1→B1 and L2→T).
- **Scope note:** these drafts are for the legacy single-stage `gen_lit` enumeration. The two-phase Stage-1 cores (`proposed_twophase/`, RI-only) would need the same exemption in their own minimality; not done.

### Alloy queries (Mac, Java 17 `a6CountOnly`/`a6CountModels`, `gtimeout 600`, one java at a time; scope `for 9 but exactly 6 Instruction, exactly 1 rBool, exactly 1 cBool, exactly 1 tBool`; regenerate with `STT_6_s4_queries.py <outdir>`)

| query | predicate | result |
|---|---|---|
| q0 | STT_6 `gen_useful_litmus` + `s4_shape` | **0** (UNSAT, 3 s) |
| q8 | STT_6 `gen_useful_litmus` + `a3c_shape` | **0** (UNSAT, 25 s) |
| q1 / q4 | `gen_useful_litmus_s4` + `s4_shape` (= boundary exemption only) | ≥ 20,000 (cap hit, 180 s); 2,000 XML in 23 s |
| q5 | RS exemption only + `s4_shape` | 0 (4 s) |
| q3 | `gen_useful_litmus_s4` and not `gen_useful_litmus` (new instances, unforced) | ≥ 20,000 (cap, 410 s) |
| q2 | `gen_useful_litmus_s4` (unforced) | ≥ 20,000 (cap, 205 s) |
| q7 | new and not `s4_shape` | non-empty; 50-sample (167 s): 50/50 are branch-transmitter S4 (T is a `Branchx`; see looseness) |
| q9 | `gen_useful_litmus_a3c` + `a3c_shape` | ≥ 20,000 (cap, 168 s); 2,000 XML in 19 s |
| q11 | `gen_useful_litmus_a3c` and not `gen_useful_litmus` | ≥ 20,000 (cap, 258 s) |

Sampled S4 shapes (50 of 2,000, seed 20261108): every one is `[committed filler] ; B0 (resolved) ; L1 ; B1 [unresolved] ; L2 ; T*`. B1 is a `Branchx` in about two thirds of them and a `Branchn` in the rest.

### Stage 2 (concretization of the 50-instance samples; llvm on the Mac, asm in the cafe2 container because the Mac has no `clang-15`)

- **Annotations resolve:** 100/100 per draft (both branch modes). Every `branch_pc` and the `xmit` address resolve; S4 transmitter kind is `ld` 50/50, A3c is `br_x` 50/50.
- **S4 blocker (Stage 2, not Alloy):** B1's condition is an immediate in **100/100** tests (`movq $1,%rsi; testq` or `xorq %rsi,%rsi; testq`), so L1→B1 is dropped and B1 is never tainted. The cause is `parsexml.py:2846-2866`: only an xm branch reads its Alloy `inreg` (phys-pinned passthrough); every other branch gets `init_op` on a vpool register. The same limitation is noted under A3b in `BUG_TAXONOMY.md`. **Proposed parsexml change (for the parsexml owner, not applied):** when a non-xm branch has an Alloy `inreg0` with an assigned physical register, use the same phys-pinned passthrough and choose the comparison so the architectural outcome is unchanged (that register is architecturally 0: `icmp eq` for `condition_value=True`, `icmp ne` for False). Guard it on the operand's architectural value being 0, as the xm path already assumes. Without this change S4 is generable in Alloy but not testable.
- **A3c:** the taint chain is intact in 100/100 (`movq %r11,%rax; testq %rax,%rax; je` with r11 = L1's result).
- **Timing / padding for S4:** padding between L2 and T is not the right knob. The existing resolve-stall sweep can place cycle N directly. B0 is a "resolved" (correctly predicted) branch, so `sweep.points` controls its stall; sweeping it densely (e.g. 0..400 step 1) moves the cycle in which B0's completion reaches commit relative to T's wake-up. B1 must have stall 0 (`sweep.unresolved_points: [0]`). With E3's `unresolved_stall_cycles: 5000`, B1's resolution is held by the hook until after B0 has resolved, so B1 squashes untainted (an A4-style path) and S4 can't occur. So E3 verbatim cannot exercise S4 even after the parsexml fix; it needs those two sweep knobs (existing config keys, no code).
- **Timing for A3c:** B1 (xm) has stall 0 and resolves when L1 returns. B2 must release in that same cycle while B0 stays held. `_inject_stalls` (`pipeline.py:411-435`) gives *every* unresolved branch the same stall, so B0 and B2 can't be separated. Needed: a per-branch unresolved-stall sweep, e.g. a `witness` role in the annotation or `unresolved_points` per PC (pipeline change, proposal only). The hook's release path re-runs the same `fetchRedirect`/`toCommit->squashedSeqNum` comparison (`gem5-hooks/stt/resolve_hooks.diff`, iew_impl.hh hunk), so a release that lands in B1's execute cycle should reproduce the "only the older squash is reported" behaviour. Event ordering within the tick is unverified.

### Upstream fix 18e304f6 (cwfletcher/stt, "fix pending squash bug"; read from the patch)

- **What it changes:** in `iew_impl.hh` `executeInsts`, a branch that is mispredicted, `isArgsTainted()`, and not `isUnsquashable()` now sets `hasPendingSquash(true)` directly and skips the `fetchRedirect`/`toCommit->squash` path. The patch comment says this stops "this tainted mispredicted branch from hiding a younger *untainted* branch misprediction (which would create a secret-dependent squash signal)".
- **A3c:** fixed by construction. A tainted B1 no longer occupies `toCommit->squash`, so B2's squash goes through.
- **S4:** unchanged. The pending squash still fires only through `getResolvedPendingSquashInst` in `commit()` (`commit_impl.hh:964-969` in e3283b9), which runs before `markCompletedInsts` untaints the wrong path. The one-cycle window (untaint in commit N, squash in commit N+1) is untouched. This matches URGENT_TODO's note that the master upgrade removes only A3c.

### A3c detection (proposal, not built)

- **What leaks:** whether B2's squash broadcasts at its own resolution (B1 correctly predicted, i.e. secret ≠ 0 under the `br_bez` encoding) or is hidden until B1's pending squash fires or B0 squashes everything (secret = 0). So the observable is B2's squash tick, or whether B2's squash happens at all, as a function of the secret.
- **`check_br` can't see it:** it keys on the *xmit* branch's own squash broadcast (`squash_by_pc[xmit_pc]`, `STAGE3_gem5/check_br.py` header and body). A correct defense never broadcasts B1's squash in-window, and the buggy one doesn't either. The difference is entirely in B2.
- **Proposed detector: a two-secret differential.** Run each test twice under the identical config and stall grid: (a) as concretized, with L1's word = 0 so B1 mispredicts; (b) with L1's word set to a nonzero value (new opt-in Stage-2/harness knob: initialize that memory slot) so B1 predicts correctly. A leak means B2's `BR:resolve_bcast` / Commit squash tick (or its presence before B0's squash) differs between (a) and (b) at some grid point. On `/work/stt-master` the two runs should match, which makes it a ready-made negative control. A cheaper first pass: in run (a) alone, flag a B2 that executed and released (`BR:resolve_release`) but had no `resolve_bcast` before B1's pending squash fired.

### What Anna must decide (also in URGENT_TODO "Manual source audit")

1. Approve `STT_6_s4.als` (one boundary exemption) and/or `STT_6_a3c.als` (one RR exemption), or reject the minimality-exemption approach. **Recommendation:** approve both as opt-in variant testsets, never replacing STT_6.
2. Approve the Stage-2 change to make non-xm branch conditions read their Alloy predicate (parsexml owner). Without it S4 can't fire. **Recommendation:** yes, as an opt-in flag first, with a byte-identical check when off.
3. Approve the A3c harness work: a per-branch unresolved-stall sweep and the two-secret differential detector. **Recommendation:** yes. Run on `/work/stt` with `/work/stt-master` as the negative control.

## 2026-11-08 — SPT_6_oneLP: conservative fix plan (proposal; nothing applied)

**Update 2026-11-08 (later, Anna asked for a consolidated SPT):** P1 + P2 + P4 + simspect-c8's perturbation-aware seed are implemented as a NEW draft file, `STAGE1_alloy/models/SPT_6_oneLP_v2.als`; `SPT_6_oneLP.als` is unchanged. P3 and P5 are not included. Cores: `proposed_twophase/SPT_6_oneLP_v2_core{,_conservative}.als`. Audit, validation and the manifest instructions: `wiki/state/EVAL_MANIFEST.md (SPT v2 brief, consolidated + deleted 2026-11-08)` §0.

Goal from Anna: be conservative, generate too many tests rather than too few. So every change below either removes only instances that cannot be realized as programs or that are provably public under SPT's own rules, or adds tests. Evidence: round-4 fixed-harness campaign on `testsets_latest/SPT_6_oneLP` (the current model, e298a9e). All 341 SPT hit tests have a transmitter operand SPT considers public: x86 slice with gem5-spt's taint rules, and gem5 never delayed a branch transmitter. Census over all 150,000 instances: `STAGE3_gem5/triage/spt_testset_shapes.py`, cafe2 `/tests/simspect_fixed_20261030/triage/r4/spt_latest_shapes.json`. Control: STT_6 shows 0 stale-rf and 0 constant-derived transmitters.

**State of A1/A2:** A2 (`rf_from_most_recent_writer`) was applied to `STT_6.als` only, on 06-03 (`STT_6.als:163`). `SPT_6_oneLP.als` and `Recon_6.als` still lack it, which is drift in the shared skeleton. A1 (the seed rewrite) was not applied anywhere.

- **P1. Add `rf_from_most_recent_writer` to SPT_6_oneLP (and Recon_6), verbatim from STT_6.als:163** (= A2). It's a sound prune, and the most important item.
  - Evidence: 102,724 of 150,000 current SPT instances (68%) have an rf edge that reads a state past a newer writer; in 69,780 (47%) that edge feeds the transmitter operand.
  - parsexml passes the newest value of the register, so the program differs from the instance (e.g. inst-086921: the model's address is the pc0 load, the program's is pc3's `imul` result).
  - Removes only instances no register machine can realize.
- **P2. Narrow declassification to the transmitted value (defense clause 2, `SPT_6_oneLP.als:349`).** This adds tests.
  - Today `- (i.operands & nonspeculative_xmit_p[p]).*(~(op_edges_p[p]))` declassifies the whole backward cone over rf and ddi, through any ALU op and through loads into memory.
  - SPT untaints far less. Paper §6 "Untaint rules": backward only through MOV, and through invertible arithmetic like ADD when all but one input is untainted; the authors call these rules conservative (no GLIFT). gem5-spt `rob_impl.hh:853-878` matches.
  - The model can't know which concrete op parsexml will pick for an `other` (random among bitnot/xor/add/imul/idiv), so the conservative rule is `.*(~(rf_p[p]))`: declassify the transmitted operand and its producer's output (the same value). The existing input rule (`:356`) then clears the value's other readers.
  - Effect: the protection set is a superset of what SPT protects, never a subset. Some new hits will be SPT legitimately untainting through a mov/add, which the x86 slicer classifies.
- **P3. Fix the one-step lag so constant chains of any depth leave the protection set (defense clause 2, `:345-357`).** Fewer junk tests; optional.
  - In one propagation step, the input rule (`:356`) and the Other-output rule (`:353`) both read the set as it was before the step.
  - So in a chain const-op → op → transmitter, the second op's input is cleared but its output stays protected for good. That's the dominant shape of round-4 "constant" hits; census: 9,626 instances (6%) with a constant-derived transmitter operand.
  - Fix: apply `:353` to the set after `:349`/`:356`/`:357`, e.g. `let o1 = o - (declassify) - (input rule) - (STLF rule) | o1 - (i & ((Otherns + Otherxs) - inreg.o1)).outreg`. That also subsumes `:351`.
  - Sound by SPT's forward rule (paper §6 "Forward (Output) Untainting"; gem5 `rob_impl.hh:236-250, 800`). To keep the model edit smallest, skip P3 and keep classifying these hits (`diag_constaddr_load`, `diag_brx_const_condition`).
- **P4. `one_insecure_speculation_scheme_p` back to STT_6's `not secure_speculation_scheme_p` in `gen_useful_litmus` (`SPT_6_oneLP.als:314`).** Adds tests.
  - SPT requires exactly one insecure transmitter, while the shared skeleton (STT_6) requires at least one. `xm` still designates the one the checker scores.
  - This is a generation change, so per CLAUDE.md it's a separate task from the protection set.
- **P5. Every input that reads a state an earlier instruction wrote must have an rf edge (new skeleton fact, all models).** Bigger; separate batch.
  - 74,621 SPT (50%) and 87,928 STT (59%) instances have such an "unfed read". Since Reg_s = physical register, the program's input gets that writer's value anyway.
  - These cause the "declassified" hits: a non-speculative load or store using the same register declassifies the value (round 4: 18 ld, 39 str, 29 br_x tests). They can also hide a tainted transmitter the model calls public.
- **Not proposed, to stay conservative:** the A1 seed rewrite to `Loads.outreg` + memory. The broad seed only ever over-protects; P3 removes the constant over-taint with a smaller edit; and a new seed risks under-protecting store-data and memory paths.
- **Keep:** stores as transmitters (`Stores.inaddr`). They have no checker yet: `str` hits are scored by check_ld's fallback as "store's pipeline complete in the window", which needs its own criterion (decision).
- **Validation before any regen** (scratch copies outside `STAGE1_alloy/models/`):
  1. Differential Alloy per change: "old-useful and not new-useful, restricted to instances with no stale rf and a load in the transmitter's cone" should be UNSAT, so nothing realizable and tainted is lost. For P2 and P4, check that new ⊇ old.
  2. Run the census on a small fresh enumeration: stale_rf → 0, and with P3 x_no_load_cone → 0.
  3. Regenerate SPT_6_oneLP from `xml` and rerun the round-4 SPT campaign. The `max_instances` cap was 150,000; if it was hit, P1 also frees room for realizable instances.

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

## ultimate (2026-11-09, audit-fanout-1109): RMW + 'addition' spec

Draft `STAGE1_alloy/models/proposed/ultimate/STT_6_rmw_u.als` + kit in `proposed/ultimate/rmw/`; NEW files only, unapproved. Decisions RJ-1..RJ-7 are in URGENT_TODO. The STT/ReCon/SPT/skeleton 'ultimate' sections will be added below when those agents report.

### Bottom line

- **Most of the RMW work already exists.** The disjoint corpus `testsets_latest/STT_6_rmw` (cafe2) is built and has been sampled on CleanupSpec (warm and cold) and on `/work/stt`. The draft `proposed/STT_6_rmwjmp.als` and its unapplied parsexml diff exist. The direct jump of RJ-1 (b) is already in Stage 2: `branch_forms.jmp_direct` in the opt-in `proposed/fv2_vocab.jsonc:124-126`, emitted at `parsexml.py:2555,2950`.
- **New Alloy result: this settles RJ-5 for the transmitter role.** In STT, every RMW Stage-1 core is an STT_6 load-transmitter core with the load relabelled as an RMW.
  - All 150 RMW cores up to 4 instructions are 100 distinct cores, every one `br_n(unresolved) → ld → rmw(xm)`. All 150 map into the STT_6 core set when the RMW is turned back into a `ld`.
  - At full scope (`exactly 6`), removing an RMW transmitter's memory operands never makes the program secure (UNSAT).
  - So the corpus, which puts `orq $0` at the same `probe_mem+secret` address, already holds every RMW-transmitter test the model can produce.
  - What a model variant adds is RMWs *off* the transmitter. All four of these shapes are SAT: a speculative RMW on the secret's or the transmitter's line (the CleanupSpec E→M shape, now produced on purpose rather than by accident), an RMW whose store half forwards to a younger load, a committed RMW before the window, and a speculative padding RMW.
- **I wrote a cleaner draft** (new file): `STAGE1_alloy/models/proposed/ultimate/STT_6_rmw_u.als` (sha256 46f9f781…). It is `STT_6.als` (7a6ac4c0…) plus a tagged RMW kind, with no TJump. The pin is one fact, so `derive_core.py` and `stage_pipeline.py` work on it unchanged (checked). With RMWs excluded, its derived core gives exactly STT_6's cores (129 raw, the same 80 distinct) at `but 3` and `but 4`.
- **Recommendation:** keep the corpus as the RMW stimulus. Fix check_ld first (`never_executed` RMW hits on STT builds are scored as leaks today), then run the corpus on E13 cold, E1, E3 and E2. Build the model variant only as a Stage-1.5 flesh of STT_6's existing 129 cores, and only if you want RMWs off the transmitter. A Stage-1 RMW run would only reproduce the corpus.
- Nothing existing was edited: no `.als`, parsexml, gem5, specs, checker or paper file. No git writes. I hold no Alloy lock and have no java running: my last batch released the lock at 01:21:26. F5 had finished on its own at 01:12:05 (UNSAT) just before the kill, and its runner removed the lock then.

### 1. What already exists

- **Corpus (C1 route (d)).**
  - How it is built: `STAGE2_compilation/make_rmw_corpus.py` rewrites the ld transmitter `movq <mem>,%r` into `orq $0,<mem>`. That gives 62,120 + 62,078 tests out of 68,093 ld transmitters per mode; about 9% are skipped (destination register live later, cqto/idivq).
  - CleanupSpec, 590-test sample: warm gives 23 hits (10 E→M, 0 textbook UV3). Cold gives 489 hit stems: 407 textbook UV3, 72 E→M, 9 UV4 split, 0 NEW.
  - `/work/stt`: 309 hits, all check_ld artifacts.
  - Diagnostic: `STAGE3_gem5/triage/diag/diag_uv3_rmw.{py,md}`.
  - Sources: claudelog 2026-11-08 "hooks-v2/rmw-corpus" and "22:35 cache-setup"; VOCAB_TABLES "RMW disjoint corpus".
- **Model draft:** `proposed/STT_6_rmwjmp.als` + `STT_6_rmwjmp.parsexml.diff.txt`. Unapplied; reviewed in section 5.
- **Decisions.** C1 is decided. Pending: RJ-1..RJ-5, the CleanupSpec E→M DECIDE, the check_ld multi-micro-op DECIDE, the cache-setup DECIDEs (count the 407, cold panics, cold as a run dimension) and C2 (2-core GETX).
- **Missing today:**
  - any RMW kind in pipeline/testrun/specs;
  - `stage_seed.py` support: `KIND_ATOM_TO_SIG` (`:50-53`) has no `TRmw`, so it would KeyError on an RMW core;
  - the check_ld fix.

### 2. What "addition" means here (my interpretation)

- **Reading A, adopted: memory-operand arithmetic.**
  - gem5 x86 microcode, from the local gem5-recon copy (`src/arch/x86/isa/insts/general_purpose/arithmetic/add_and_subtract.py`):
    - `ADD_M_R` = `ldst t1; add t1,t1,reg; st t1` (`:86-91`);
    - `ADD_M_I` = `limm t2,imm; ldst; add; st` (`:48-54`);
    - `ADD_LOCKED_M_R` = `mfence; ldstl; add; stul; mfence` (`:101-108`). It never runs speculatively: `Ldstl` is `nonSpec=True`, stt_e3283b9 `ldstop.isa:486-489`;
    - the load-op `ADD_R_M` = `ld t1; add reg,reg,t1` (`:120-124`).
  - The OR forms have the same shapes. `OR_M_I` starts with `limm` in the STT, CleanupSpec and SPT trees too (`logical.py:44-49`).
  - So "RMW and addition" means two things:
    - (i) the RMW's ALU op: `orq` vs `addq`, value-neutral with a 0 source vs value-changing. This is a Stage-2 choice (RJ-6).
    - (ii) the load-op `addq (mem),%r`. I recommend Stage 2 only (RJ-7).
- **Reading B: the register `addq`** (a real flag-setting ADD; today's `add` is emitted as LEA). It matters for SPT:
  - gem5-spt untaints backward only through `add,addi,adc,adci,sub,subi,sbb,sbbi` (`spt_0d2be0f/src/cpu/o3/rob_impl.hh:854`);
  - flags make `inc` a two-source op (audit A1).
  - This is Stage-2 vocabulary (G2 / FV-5; `inc` already exists in `fv2_vocab.jsonc`), not an Alloy kind.
  - SPT-relevant consequence: an RMW `add` µop is in that invertible list and an `or` is not, so `addq` and `orq` RMWs differ for SPT backward untaint. This is by reading only, untested.
- **Reading C: "RMW as an addition to the model".** This is section 3.
- **Reading D, not adopted: variable-time arithmetic as a transmitter.** That is the dormant `Otherxs`. gem5-spt treats non-memory instructions as transmitters only with `--moreTransmitInsts=1` (strict `readyToIssue_UT`, `inst_queue_impl.hh:1549-1583`), and E11 sets 0.

### 3. The spec

#### 3.1 Alloy: `ultimate/STT_6_rmw_u.als` (line numbers are in that file)

**Skeleton (S).** Kind-generic, to be pasted verbatim into every family. With no RMW atoms, every line reduces to the STT_6 line it replaces.
- `one sig TRmw extends InstrType {}` (`:57`) and `fun Rmws : Instruction { kind.TRmw }` (`:99`).
- Operand shape, for x86 `orq|addq %src,(m)` / `$imm,(m)`:
  - `fact rmw_ops {no Rmws.outreg}`;
  - `fact rmw_mem {all r: Rmws | one r.inmem and one r.outmem and r.inmem.opstate = r.outmem.opstate}` (both halves on one location);
  - `fact rmw_inreg {all r: Rmws | lone r.inreg}` (`:151-153`);
  - `limited_ins` becomes `all i: Instruction - Rmws | #(i.ins) <= 2` (`:160`).
- Data flow: `fact rmw_ddi {no (Rmws.operands <: ddi) - ((Inmem+Inreg)->Outmem)}` (`:212`). It is optional, like every kind's ddi; the address flows nowhere.
- The unused helpers `no_unresolved_mem` / `no_unresolved_mem_p` count RMWs (`:180`, `:297`).
- Everything else applies unchanged:
  - the rf rules (`constrainrf`, `same_state_rf`, `rf_from_most_recent_writer`) and `unidirectional_rf`, which stops an RMW reading its own write;
  - RI stitches inmem→outmem through `fix_rf_hole_p` exactly as for a ld/st pair;
  - RS removes both memory operands.
- To port to `SKELETON_u.als`: the same lines, plus `spec_loads_p` (`SKELETON_u.als:323`) becomes `(Loads+Rmws) & speculation_contract_p[p]`. The ultimate STT and ReCon blocks seed protection from `spec_loads_p[p].(inmem_p[p])` (`blocks/STT_6_u_stl.block.als:17`, `blocks/Recon_6_u.block.als:24`).

**Which half transmits: the load half.**
- `ldst` is a load micro-op on every build (`defineMicroLoadOp('Ldst', … StoreCheck)`, stt_e3283b9 `ldstop.isa:483-485`). It reads the cache speculatively, and on the Ruby builds it is an exclusive GETX.
- The store half writes the cache only at retirement on all these builds.
- SPT also counts the `st` µop's address as a transmitter (`isMemTransmit() = isLoad()||isStore()`, spt `base_dyn_inst.hh:731`). That is the same address, and store-address transmitters are out of scope anyway (KV3, Anna 2026-11-08).
- Taint flow: the data, (loaded value op src), flows into memory through the store half. That matters only for SPT and STL.

**Defense classification (D), per family.**
- **STT_6** (state-based; this is what the draft contains):
  - `leakage_function = (Loads+Rmws).inaddr + Branchxs.inreg` (`:381`);
  - propagation `s - ((Loads+Rmws) & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate` (`:387`): a non-speculative RMW declassifies its location like a load;
  - contract and policy unchanged;
  - sources: stt_e3283b9 `base_dyn_inst.hh:675-676` (`isAccess()`/`isTransmit()` = `isLoad()`); STT p9 §6.4 and p5 §6.1.
- **STT instance-based** (STT_6_v2 / STT_6_u [u-4]): seed `((Loads+Rmws) & speculation_contract_p[p]).inmem & o_p[p]`; same leakage line; propagation unchanged.
- **ReCon** (Recon_6_v2 / Recon_6_u):
  - seed as instance-based STT, minus revealed reads;
  - in `revealed_p`, the re-load is `(Loads+Rmws).inmem`;
  - LD2 may be an RMW. The Reveal is sent from `LSQUnit::commitLoad` for a committing load whose renamed source matches the load-pair table (local gem5-recon `lsq_unit.cc:851, 870-911`), and the ldst is in the LQ;
  - LD1 is `Loads` only (an RMW has no outreg);
  - the concealer is `Stores+Rmws` (§4.4);
  - leakage as STT.
- **SPT** (v3 / SPT_6_u):
  - leakage gains `Rmws.inaddr`;
  - the stored value is public iff both the loaded value and inreg are public;
  - in the STL rules, an RMW is a store whose data is (loaded op src), and a load with no outreg;
  - backward untaint goes through the RMW's ALU µop only for `add`.
  - This needs the ultimate SPT block's structure (RJ-3).
- **STL family:** is an RMW's store half an unresolved-address store? See RJ-3.
- **CleanupSpec, InvisiSpec, SpecLFB, DoM, Doppelganger:** these run STT tests, so the STT (D) applies.

**Pin (R).** `fact rmw_pin { some Rmws }` (`:359`). It is a fact so the run block stays the exact text `run gen_lit {\n  gen_useful_litmus\n}` that `derive_core.py:89` and `stage_pipeline.py:58` anchor on.

#### 3.2 Two-stage interaction (RJ-4)

- **Stage 1.** `derive_core.py --minimality ri` works on the draft unchanged. Re-deriving STT_6 the same way reproduces the repo's `STT_6_core_ri.als`, ignoring comments.
  - The core inherits the pin, so Stage 1 yields RMW cores only: 150 raw / 100 distinct, all exactly 3 instructions.
  - Their inreg: absent in 20, present but unfed in 40, fed by the same load in 40.
  - An RMW as an essential non-transmitter: UNSAT at ≤4 (11-08 agent), and impossible at any bound in STT_6 by argument. A younger load's own read is already protected, so removing an RMW never secures a leak.
- **Stage 1.5.** The flesh model is `STT_6_rmw_u.als`, and the needle is intact. The fact forces at least one RMW into every fleshed instance, so fleshing STT_6's 129 cores puts RMWs off the transmitter.
  - RS-minimality forces every RMW onto an essential state. So a padding RMW always sits on the secret's slot (constant address) or uses the transmitter's address register. It can never land on an unrelated line.
- **Tooling:** add `'TRmw': 'Rmws'` to `stage_seed.py:50-53` before any Stage-1.5 run.

#### 3.3 Stage 2 (parsexml; all approval-gated, none applied)

1. **Kind map.** `_TYPE_TAG_TO_KIND` (`parsexml.py:100-113`) gets `"TRmw": "rmw"`. Without it an RMW becomes `unknown` → other_n, an ALU op with `xmit.kind:"unknown"`. Never feed RMW XML to today's pipeline.
2. **Table.** Category `"rmw"` with candidates `rmw_or` (`orq src,(a)`) and `rmw_add` (`addq src,(a)`), both `uses [inreg0, inaddr, inmem, outmem]`. Never lock/xchg.
3. **Pass 5** (the diff's `rmw_or` branch, generalized):
   - one inline asm, with the pc marker and lc/fnc labels on the RMW itself;
   - address `(%probe_base,%inaddr,1)` if inaddr is specified, else `idx*8(%mem_base)` from the outmem (= inmem) slot;
   - source = the pinned register of a specified inreg0;
   - **a blank inreg0 becomes an explicit `i64 0` input with an `r` constraint**, not `$0` and not a free-pool register. `$0` gives `OR_M_I`/`ADD_M_I`, whose independent leading `limm` caused the 309 artifacts. A free-pool register can be fed by interleave or fanout chains, which would make the RMW value-changing. The register form starts with `ldst`.
4. **probe_mem check** (`:2218`): add the rmw names.
5. **Needed hunks the 11-08 diff predates:**
   - the fanout-v2 transmitter slot (`:2382`, `("load","store")`): add the rmw names, or the splice bias goes to the RMW's ALU source instead of its address;
   - store separation (`:2229-2244`) looks only at `"store"`: treat an RMW as a writer.
6. **`_stl_arch_values`** (`:1114`): `rmw_or` = `mem |= src`, `rmw_add` = `mem += src`. Pass 2.6 STL pairing stays ld/str only (fine for STT_6).
7. **Annotations and labels.** `xmit.kind = "rmw"`. The RMW is the first instruction after its label, so `compile_annotate.py` resolves it correctly. Jumps need nothing (`jmp_direct` exists). Interleave chains keep their fixed names.
8. **Load-op** (Reading A-ii): Stage 2 only, as the existing `load_op_add` ld candidate (VOCAB G4; V5 zeroes the destination first). Its first µop is `ld`, so the check_ld artifact cannot happen. On Ruby it is a plain read, so it is not a UV3 stimulus.

#### 3.4 Checker

1. **`pipeline.py:313-320`:** add `"rmw": "check_ld.py"`. Today it falls back to check_ld anyway.
2. **check_ld multi-micro-op fix** (the existing DECIDE, option (a)).
   - The bug: `check_ld.py:87` falls back to `xmit_complete` taken from `best_record` over every µop at the pc (`gem5_common.py:822-836`; `parse_pipeview` `:503-524` drops upc and seq). The data-obtained gate runs only when `xmit_execute > 0` (`check_ld.py:145`). So a delayed, never-executed `ldst` is scored by the `limm`'s completion.
   - The fix:
     - (i) when LSQ records exist at the xmit pc, use the pipeview record whose seq equals the LSQ `sn` (`parse_lsq` `:621+` keeps `sn`; `parse_pipeview_by_seq` `:587-618`);
     - (ii) apply the gate whenever LSQ records exist (`fate is not None`), so `never_executed` is never ungated;
     - (iii) record the chosen seq and upc.
   - Validation: re-score the `/work/stt` RMW sample (expect 309 → 0) and one non-RMW campaign (expect identical verdicts).
3. **Kind plumbing.** `testrun.py:72` partitions by kind, so RMW hits land in `<mode>/rmw/`. Dashboards that hard-code ld/br_x/other_x need the new kind. `specs/transmitter_criteria.json` "kinds" needs an `rmw` entry mirroring `ld` (a spec edit, so it needs approval).
4. **Footprint builds.** `check_footprint` is unchanged and `diag_uv3_rmw` exists. E→M needs its own known-cause diagnostic (the existing DECIDE). With RMWs off the transmitter, the D2 footprint-attribution question starts to matter.

#### 3.5 Runs

- **Corpus, now:**
  - E13 CleanupSpec, warm and cold (counting is gated by the UV3/E→M DECIDEs);
  - E1 Unsafe as the positive control (every RMW transmitter should leak);
  - E3 STT upstream and E2 Recon-STT, after the check_ld fix;
  - E12a, E12b and E14 as cheap controls (the 11-08 demos say they protect it like a load);
  - not E11 or the STL builds.
- **Variant, only if approved:** Stage-1.5 flesh of the 129 STT_6 cores with the patched Stage 2. Run E13 cold first (F6/F9 shapes), then E3/E2. Never mixed into STT_6 (C1).

### 4. Does the STT_6_rmw corpus already answer it? (RJ-5)

- **For the RMW as transmitter: yes.**
  - Every RMW core relabels to an STT_6 ld-transmitter core (150/150).
  - The RMW transmitter's memory operands never matter for the leak (F5/K1 UNSAT).
  - Its address is `probe_mem+secret`, the same as the corpus's.
  - The only differences: the optional source register (data, which changes only probe memory) and the ~9% of ld transmitters the corpus skipped because the destination register is live later.
- **For RMWs elsewhere: no.** The corpus has none: no E→M with a plain-load transmitter and a younger RMW on its line (F9), no RMW as an STL source (F7), no committed RMW before the window (F4), no speculative padding (F3/F6).

### 5. Review of `STT_6_rmwjmp.als` and its diff

- **Correct and well structured.** The RMW semantics (same-location operands, ddi, no outreg, 3 ins) and the STT classification are right and the sources check out. It follows "defense block only + duplicated skeleton": the (S) lines are kind-generic and the (D) lines sit only inside the defense block.
- **Problems:**
  1. `TJump` duplicates a resolved, operand-less `br_n` (its own finding), and Stage 2 now does jumps, so drop it.
  2. Renaming the command to `run gen_lit_rmwjmp` breaks the `derive_core.py:89` and `stage_pipeline.py:58` anchors. The two-stage route that RJ-4 recommends therefore can't be built from it without hand edits.
  3. With TJump kept, the pin `has_rmw_or_jmp` is satisfied by jumps alone. Its own first 200 instances were all jump-only.
  4. `limited_rmw_ins` and `jmp_not_xm` are redundant.
- **The diff** still applies (dry run on copies: offsets +23/+151/+478, fuzz 1), but:
  - it lacks the two hunks in 3.3 item 5;
  - it duplicates `jmp_direct`;
  - its blank-source fallback is `orq $$0`.
- **Verdict:** sound, but superseded by `STT_6_rmw_u.als`.

### 6. Alloy evidence (Mac, Java 17, alloy6.jar, symmetry 80; scratch queries; log copied to `ultimate/rmw/rmw_alloy_runs.log`)

| query | result |
|---|---|
| STT_6_core_ri at `but 3` / `but 4` | 129 / 129, exhausted (4 s / 45 s) |
| RMW core, `no Rmws`, `but 3` / `but 4` | 129 / 129, exhausted; the canonical sets equal STT_6's (80 distinct) |
| RMW core, pinned, `but 3` / `but 4` | 150 / 150, exhausted (3 s / 21 s); 100 distinct; 150/150 relabel into the STT_6 core set (10 distinct ld-transmitter images) |
| F1 pinned, `exactly 6` | SAT; cap 300 in 11 s. xm: br_x 129, rmw 74, ld 97. 187 speculative padding RMWs, 30 RMW STL sources; every RMW shares a Mem state with a load |
| F2 RMW = xm / F3 speculative non-xm / F6 speculative ld then RMW on the same location / F7 RMW store → younger ld / F8 xm with fed source / F9 non-xm RMW from the same producer as the ld transmitter | all SAT, 30 each, 3-6 s |
| F4 committed RMW | SAT, 1 instance, then a 120 s timeout |
| F5: RO on xm-RMW inmem+outmem makes it secure? (`exactly 6`) | UNSAT, 237 s, decided during translation |
| controls: K1 = F5 at core `but 4`; K2 / K3 = RO on inaddr at core / full scope | K1 UNSAT; K2 SAT (100); K3 SAT (5 in 3 s), so the query shape is not vacuous |

Not run, to free the lock: RMW cores at `but 5/6`. STT_6's own cores stop at 3 instructions (EVAL_MANIFEST.md:42).

### 7. Decisions for Anna (folding RJ-1..RJ-5)

- **RJ-1, TJump.** It is already realized as Stage-2 `jmp_direct`. **Recommendation:** close RJ-1 as (b) and keep TJump out of every model.
- **RJ-2, scope.** STT_6 first, RMW kind only. **Recommendation:** unchanged.
- **RJ-3, classification.**
  - STT as drafted: the address transmits, and a non-speculative RMW declassifies.
  - ReCon: an RMW can be LD2, not LD1, and its store half conceals.
  - SPT: wait for the ultimate SPT block; `add` and `or` differ.
  - STL, is the RMW store half an unresolved-address store: (a) yes, (b) no for now, (c) decide with the STL checker.
  - **Recommendation:** approve STT; approve ReCon when Recon_6_u is approved; STL (b).
- **RJ-4, pins.**
  - (a) fact pin at both stages, as drafted;
  - (b) pin at Stage 1.5 only, flesh model `STT_6_rmw_u` seeded with STT_6's 129 cores, and skip RMW Stage 1 because it equals the corpus;
  - (c) no pin, which mostly re-produces STT_6.
  - **Recommendation:** (b).
- **RJ-5, corpus vs variant.**
  - (a) corpus only;
  - (b) corpus plus a Stage-1.5 variant;
  - (c) the full variant.
  - The evidence is in section 4. **Recommendation:** (a) now; (b) if you want E→M on purpose, an RMW as an STL source, or committed RMWs; never (c).
- **RJ-6 (new), Stage-2 value semantics (the "addition" choice).**
  - (a) value-neutral only: `or` with an explicit zero, as in the corpus;
  - (b) `or`/`add` at random; the Alloy-specified source when inreg is specified, an explicit zero when it is blank;
  - (c) forms that always change the value (`addq $1,(m)`).
  - **Recommendation:** (b). The value then changes exactly where Alloy's ddi says the stored value depends on a register.
- **RJ-7 (new), the load-op `addq (mem),%r`.**
  - (a) Stage-2 `load_op_add` only;
  - (b) an Alloy `TLdop` kind. It would be a relabelled ld under RI, the same argument as for jumps and for RMW cores (argued, not run).
  - **Recommendation:** (a).
- **Prerequisites already listed in URGENT_TODO (not duplicated here):** the check_ld multi-micro-op DECIDE (recommend (a) as specified in 3.4, plus the register-form emission); E→M (recommend (b), its own diagnostic); counting the 407 cold UV3 hits; cold panics; cold as a run dimension; C2.

### Files

- New (repo; unapproved; nothing else touched):
  - `/Users/annaeaton/trippel/simspect/STAGE1_alloy/models/proposed/ultimate/STT_6_rmw_u.als`
  - `/Users/annaeaton/trippel/simspect/STAGE1_alloy/models/proposed/ultimate/rmw/`, a reproducible kit: `make_rmw_u.py`, `STT_6_rmw_u_core_ri.als` (derived core), `make_queries.py`, `run_batch.py`, `analyze.py`, `relabel_check.py`, `pretty.py`, `rmw_alloy_runs.log`.
- Scratch only, throwaway: `/private/tmp/claude-501/-Users-annaeaton-Documents-stanford-trippel-simspect/3e17c539-dd1e-4f38-805e-ce336a0f23ff/scratchpad/agents/rmw/` (queries, instance outputs, patch dry-run copies).
- I did not write the claudelog/claudenotes entries; that is left to the coordinator. After the coordinator writes it up, Anna should run `make sync`.

## ultimate (2026-11-09, ultimate-recon-spt): ReCon (`Recon_6_u`, `Recon_6_u_stl`) and SPT (`SPT_6_u`) — DRAFTS, unapproved

Resumed from the files the stopped audit-fanout-1109 agents left in `STAGE1_alloy/models/proposed/ultimate/` (their reports were never delivered; the ReCon agent's unfinished draft report was recovered from its scratch dir and is folded in here). Nothing existing was edited. All runs: Mac, Java 17, `alloy6.jar`, under the shared one-java lock, capped by `gtimeout`. Logs: `proposed/ultimate/queries/recon/runs.log` (ReCon), `proposed/ultimate/queries/spt_runs.log` (SPT). Scratch for this pass (Stage-2 smoke, partition check, the v3 b4 copy) was `_scratch_ultimate_recon_spt/` at the repo root, now deleted.

### ReCon ultimate — state and verdict

**What it is.** `Recon_6_u.als` = the STT agent's `STT_6_u.als` (sha256 529511a1…) plus ONE ReCon delta in defense clause 2, built by `queries/recon/make_recon_u.py` (anchored, hash-checked; `diff STT_6_u.als Recon_6_u.als` = header, block title, three functions, the seed line). `Recon_6_u_stl.als` = `STT_6_u_stl.als` (f08dad0c…) plus the same delta. Cores `Recon_6_u_core_ri.als` / `Recon_6_u_stl_core_ri.als` = `proposed_twophase/derive_core.py --minimality ri` of those (re-derived in this pass: byte-identical). `blocks/Recon_6_u.block.als` = the same block in the `SKELETON_u` interface (skeleton agent's scope; not a candidate for the clean runs).

**Semantics vs `Recon_6_v2.als` (model-fixes).** Identical except [u-8]: a store whose ADDRESS is unresolved does not conceal (the re-load may bypass it and read the old, revealed value; ReCon §4.5.2 Table 1 case 1). In the spectre flavor this changes no generated instance (g10: any generated instance with an unresolved store, UNSAT in 77 s), so `Recon_6_u` ≡ `Recon_6_v2` on the testset; it matters only for the STL flavor (s2: without [u-8] every "bypass reads the revealed value" test is a guaranteed false positive on a working ReCon). The rest is a refactor (`recon_ld1_p`, `recon_concealer_p`) and much longer source comments.

**Does the reveal rule match the paper?** Yes, clause by clause (paper `~/Documents/quail/sources/papers/aimoniotis-2023-recon.pdf`, ACM HTML print without page numbers, cited by section, as the 2026-11-08 audit did): direct pair only, "RECON limits its detection to only the leakage of load pairs with a direct dependence" (§4.3) = `ld1.outreg.rf & ld2.inaddr` (one rf edge); at LD2's commit, "When the second load (LD2) of a load-pair commits, the address accessed by the first load (LD1) is marked as revealed" (§5.2; §5.1 "we opt for implementing load-pair detection in the commit stage") = `ld2: Loads & committed_p[p]`; per word (§5.2 "a bit vector with each cache line to mark the data words") = per `Mem_s`; conceal on store, "Once an address is revealed, it is guaranteed to be safe as long as its contents do not change" (§4.4), "upon the commit of a store instruction, the bit of the corresponding word is cleared" (§5.2), and a store-forwarded load "always receives concealed data" (§4.4.2) = any resolved/committed store to the word between LD1 and the re-load. Only the re-load's memory read is un-protected (§5.4 "for STT, any load that receives a revealed value untaints its destination register").

**Verification (all on disk in `queries/recon/runs.log`).**

| Query | Asks | Result |
|---|---|---|
| g0_gen_sat / s1_stl_gen_sat | flat `gen_lit`, spectre / stl | SAT, 20 instances each (3 s / 2 s) |
| c1_core_b3 | `Recon_6_u_core_ri` at `but 3`, exhaustive | 129 (= Recon_6_v2_core_ri = the STT RI cores) |
| fa_true_reveal (+ STT control) | committed direct pair on A, speculative re-load of A is xm's only source | UNSAT (not flagged) / STT_6_u SAT |
| fb1 / fb2 / fb3 | + committed store after LD2 / in-flight resolved store / store between LD1 and LD2 | SAT / SAT / SAT (concealed → flagged; fb3 = the R-SA-2 stale-reveal test) |
| fb4 (+ v2 rule) | only an unresolved-address store between | UNSAT ([u-8]) / SAT under the v2 rule |
| fc | LD1 → ALU → LD2 committed (no direct pair) | SAT (no reveal) |
| fd2 | LD2 in flight | SAT (no reveal before commit) |
| fr1_qr1a / fr1_qr1a_old | audit QR1a (R-1) on Recon_6_u / today's Recon_6 | SAT (fixed) / UNSAT (reproduces the audit) |
| fotb_full | full getOldestTaint gadget | SAT (flagged) |
| s2 / s2 STT control / s3 (stl) | bypass reads revealed value / control / concealed by a committed store | UNSAT / SAT / SAT |
| g1–g5 | generated (with minimality): in-flight LD2, R-1, concealed reveal, ALU near miss, OTB hook point | SAT each |
| g10 | generated instance with an unresolved store | UNSAT (77 s): [u-8] is inert in the spectre flavor |
| d1_recon_only | Recon_6_u-useful, not STT_6_u-useful | 50 (cap); `show_inst.py --summary`: 50/50 = in-flight-LD2 (pairU, d2) |
| d2_stt_only | STT_6_u-useful, not Recon_6_u-useful | 50 (cap); 50/50 = committed pair + re-read (true reveals, the tests a working ReCon may release) |
| d3_gained_vs_old | Recon_6_u-useful, not old-Recon_6-useful | 50 (cap); 50/50 carry the R-1 shape (21 also an in-flight pair) |
| fx_old_sub_new | completeness: every operand old Recon_6 flags, Recon_6_u flags too (facts only, exactly 6) | **timed out (900 s, rc 124), no counterexample; not a proof.** By reading it holds at no_p: old Recon_6 protects a word X only if no non-speculative load reads X anywhere (its fold runs over every position and its reveal is a no-op), and a Mem_s reaches a transmitter only through a load's Inmem; that load is speculative (Recon_6_u seeds it) and cannot be revealed, because a reveal needs a committed LD1 reading X, which would have removed X in the old model |
| fx_new_minus_old_not_r1 | every transmitter Recon_6_u newly flags is an R-1 witness | **timed out (600 s, rc 124), no counterexample; not a proof** (d3's 50 samples are all R-1 shapes, consistent with it) |
| Stage 1.5 smoke | `Recon_6_u.als` + one `c1_core_b3` core pinned by `stage_seed.py`/`stage_pipeline.build_seeded_model` (exactly what `launch_stage15.py` does) | **not run** (stopped at wrap-up; the seeded model was built without error, which is the part that can break) |

The first `fx_*` attempt (01:20) died on a query-file syntax error; the files were regenerated at 01:46 and the rerun was killed when the session stopped. Both were rerun in this pass by the orphaned runner (see "Process note") and both timed out.

**Stage 2 smoke (scratch, no corpus writes).** `batch_generate.py` on the 20 `g0_gen_sat` instances (both branch modes) = 40/40 ok, and on the 20 `s1_stl_gen_sat` instances in `stl_bypass` = 20/20 ok; all 60 `.ll` compile with `llc -mtriple=x86_64-linux-gnu` (Mac llc, not the container's clang-15; asm/gem5 not run). **Two-stage compatibility:** `partition_stage1.py` (the cafe2 partitioner) splits both RI cores into the usual 10 partitions (kinds Branchxs, Loads), the same layout cafe2 uses for `Recon_6_core_ri` / `Recon_6_stl_core`.

**Recommendation (ReCon): adopt `Recon_6_u.als` and `Recon_6_u_stl.als` for the clean runs** (over `Recon_6_v2`: same testset in the spectre flavor, and the only version whose STL flavor does not manufacture false positives; over the current `Recon_6.als` / `proposed/Recon_6_stl.als`: those keep the unsound location fold R-1 and a no-op reveal R-2, and `Recon_6_stl` also lacks the rf fact). It is only coherent together with `STT_6_u` (the STT agent's section): the [u-1] skeleton lines and the seed are shared, so the two stay one diff apart. If `STT_6_u.als` changes again, re-run `make_recon_u.py --force --cores` (it refuses on a hash drift).

**Defense-block diff vs current `Recon_6.als` (three clauses).**
- (1) speculation contract: unchanged (`uncommitted_p[p] & has_unresolved_brs_p[p]`). Stl flavor: unchanged semantics vs `proposed/Recon_6_stl.als` (`u_store_shadow_p` = `has_unresolved_strs_p`, moved from the skeleton region into the defense block, together with the two stl flavor facts, verbatim).
- (2) protection set: seed `Mem_s - (~opstate).(^(op_edges_p[p]).(~inaddr).(Loads-speculation_contract_p[p]))` (State-typed, a no-op) → `((Loads & speculation_contract_p[p]).inmem & o_p[p]) - revealed_p[p]` (Operand-typed: every speculative load's read, minus reads revealed by a committed direct pair and not concealed); propagation `s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate` (the R-1 location fold) → identity `o`.
- (3) leakage function: unchanged (`Loads.inaddr + Branchxs.inreg`).

**Outside the defense block (flag):** [u-1] four skeleton lines change State → Operand (`a`, `last_committed_protset_p`, `secure_speculation_scheme_p`, `tag_xm`; the form SPT v2 already uses); everything else is byte-identical to `Recon_6.als` as it is today (with the rf fact). Headers/comments only otherwise.

**Superseded once applied:** `Recon_6.als`'s defense block and `proposed/Recon_6_stl.als`; `proposed/Recon_6_v2.als` + `proposed_twophase/Recon_6_v2_core_ri.als` (keep as provenance); the running/finished cafe2 Stage-1 families `Recon_6_core_ri` and `Recon_6_stl_core` (pre-fix models).

**Open ReCon follow-ups (not model changes; from the recovered report).** F1: one-pass timing runs the speculative re-load before LD2 retires and gem5-recon has no retroactive reveal (`updateRevealedTaints` has no caller), so no reveal can be observed on E6 until Stage 2 delays the re-load (URGENT B4). F2: probe-addressed loads all read `probe_mem[0]` (`parsexml.py:2626-2642`), so on ruby3 one committed pair can reveal words the model keeps distinct → possible E6 false positives; a `diag_recon_probe_alias_reveal` bucket first, a Stage-2 load-separation option later. F5: E2 (classic Recon-STT) uses the STT_6_u testset, E6 (ruby3) the Recon_6_u testset.

### SPT ultimate — state and verdict

**What it is.** `SPT_6_u.als` = the approved `SPT_6_oneLP_v2.als` (acb1f2e2…) with ONLY the defense block replaced (`make_spt_u.py`, hash-checked; skeleton byte-identical, verified in this pass). Clause 2 becomes SPT's converged taint: everything tainted unless a rule proves it public, iterated 6 steps to a fixpoint; the protection set handed to the skeleton is the set of tainted transmitter operands, which have no outgoing edges, so the skeleton's transitive `^op_edges` term is vacuous (= audit S-1 **Option B**, without a skeleton edit). Rules: [u-2] declassify only the ADDRESS of non-speculative loads/stores (no longer br_x predicates: gem5-spt never declassifies them, audit B1); [u-3] backward untaint on a new SPT-only subset sig `InvOp` (an ALU Stage 2 must emit as `movq` / `movq+addq|subq`) with a canonicalizing fact `spt_invop_class`; [u-4] store→load untaint both ways gated by STLPublic and "store uncommitted"; [u-5] forward untaint to the fixpoint (fixes the P3 one-step lag); [u-6] initial registers public.

**It is not S-1 Option A.** Option A is `proposed/SPT_6_oneLP_v3.als` (one line: also declassify the producer load's `Inmem`), which Anna approved "for now". `SPT_6_u` is Option B plus S-2/P3, S-3, S-5 and B1 fixes. On the v2 sample (`results/spt_v2_20261108`, 3,000 v2 instances, re-scored by the independent re-implementation `queries/spt_semantics.py`; result file was in the dead session's scratch): 2,709 agree; 291 v2-useful instances are not u-useful — 288 `P3_const` (xm's value has no load in its backward cone, so SPT forward-untaints it: a v2 false positive, 96 each for Load/Store/Branchx transmitters) and 3 `S1_declass` (the S-1 shape that v3 also removes). No u-only instance can appear in that direction by construction of the sample; the reverse differential (`spt_C_gained`) was never run.

**Stage-1 convergence (the simspect-c8 DECIDE).** v2's RI core gave k3 = 546 and k4 ≈ 145,000 (cafe2 partition capped at 200,000; sampled k4 cores were load-free ALU/branch chains over initial registers, exactly the `P3_const` class). Counts on the Mac (`but k` = up to k instructions, so comparable to cafe2's k1..k):

| core (RI-only) | `but 3` | `but 4` |
|---|---|---|
| `SPT_6_oneLP_v2_core_ri` (cafe2) | 546 | ≈145,000 at k4 alone (capped run) |
| `SPT_6_oneLP_v3_core_ri` (Option A) | 393 (model-fixes) | **not run** |
| `SPT_6_u_core_ri` (ultimate) | **not run** | **not run** (queued; stopped at wrap-up before it got the lock) |

Convergence check of the 6-step fixpoint (`conv_nop`: 7 steps ≠ 6 steps at no_p, exactly 6): **not run**; the 6-step depth is the SPT agent's claim (its `qconv` query was never executed), so the fixpoint is unverified.

**Cores.** The SPT agent derived `SPT_6_u_core.als` as a *conservative* core (no RO/RI), but the cafe2 pipeline runs RI-only cores for every family (EVAL_MANIFEST "Stage-1 minimality: RI-only for every family", `SPT_6_oneLP_v2_core_ri`). I derived `proposed/ultimate/SPT_6_u_core_ri.als` (new file, `derive_core.py --minimality ri`; identical to the agent's `queries/spt_D_uri_b4.als` except the scope) and checked that `partition_stage1.py` splits it into the usual 12 partitions (Branchxs, Loads, Stores). `SPT_6_u_core.als` (conservative) is not what the pipeline consumes. The queued count runs (`spt_D_uri_b3/b4`, a v3 `but 4` copy, `conv_nop`) were stopped at wrap-up before they ran; each is a single capped command for the next pass (`MODE=count LIMIT=200000 bash queries/run_spt_queries.sh 900 queries/spt_D_uri_b4.als`).

**Stage 2 smoke.** **Not run**: no `SPT_6_u` instances were produced in this pass (the flat `gen_lit` run never got the lock). Stage 2 must at least tolerate the extra `InvOp` sig in the XML; unchecked.

**Stage-2 contract caveat (needs the parsexml owner).** `InvOp` is a new atom class Stage 2 does not read today: `parsexml.py` picks an ALU's concrete op at random among add/xor/bitnot, so an `InvOp` may come out as `xor` (gem5 keeps it tainted: lost coverage, not a false hit) and a non-InvOp ALU may come out as `add` (gem5-spt backward-untaints it while the model protects it: a false-positive hit, the same S-5 class v2 already has). So `SPT_6_u` is no worse than v2 without the parsexml change, and right only with it (InvOp → `movq`/`movq+addq`, other ALUs → `imulq`/`andq`/`orq`).

**Recommendation (SPT): **`SPT_6_oneLP_v3.als` (Option A), single-stage, for the clean runs that start now; `SPT_6_u` is the next-round candidate, not ready.** Evidence: v3 is the version you approved "for now", is one line from the approved v2, and was validated by model-fixes (Q1 UNSAT except the store-forwarded residual; RI cores 546 → 393 at `but 3`). `SPT_6_u` has the better semantics on paper (it removes the 288/3000 `P3_const` false positives that v2 and v3 both keep, the S-1 residual, and B1) but nothing about it has run in Alloy this round (no generation, no core counts, no convergence check), and it needs a parsexml change to mean what it says. **SPT testset verdict: there is still no evidence that any SPT model gives a bounded two-stage testset.** v2's k4 blow-up consists of load-free `P3_const` chains, and v3 does not touch P3, so v3's RI core will very likely blow up the same way (v3 `but 4` never counted); `SPT_6_u` is the only draft that removes that class, so it is the one with a real chance of converging, but that is a hypothesis. Hence single-stage for SPT now (production model, `gen_lit` at exactly 6, the 300k cap: option (b) of the simspect-c8 DECIDE), with the `P3_const` hits bucketed as a known model false positive.**

**Defense-block diff vs current `SPT_6_oneLP_v2.als` (three clauses).**
- (1) speculation contract: unchanged.
- (2) protection set: seed `o_p[p] - ((Inreg + Inaddr) - i_p[p].outreg.(rf_p[p]))` + the 7-step fold with v2-4 declassification and one-step forward/STL untaint → seed `leakage_function_p[p] - spt_public_p[p]` (tainted transmitter operands; `spt_public_p` = 6-step fixpoint of declassification [u-2], forward [u-5], backward-on-InvOp [u-3], STL [u-4], over one-register-one-taint closure), propagation identity. Plus, inside the defense block, `sig InvOp in Instruction` and `fact spt_invop_class` (these change the instance space: an extra subset per ALU, canonicalized).
- (3) leakage function: unchanged (`Loads.inaddr + Branchxs.inreg + Stores.inaddr`).

**Outside the defense block:** nothing (skeleton byte-identical to v2).

### Apply for clean runs (each `.als` step needs Anna's own sign-off; Claude applies nothing)

ReCon (needs `STT_6_u` applied the same way first; Anna OK'd STT_6_u per the coordinator):
1. Sign-off R-U1: `Recon_6.als` becomes `proposed/ultimate/Recon_6_u.als` (defense block above plus the four [u-1] skeleton lines). Either copy `Recon_6_u.als` over `STAGE1_alloy/models/Recon_6.als` (keep the old one as `Recon_6_pre_u.als`), or add it as `STAGE1_alloy/models/Recon_6_u.als` and point the configs and `specs/alloy_models.json` at it. Recommendation: a new file plus a pointer, so old results keep their model.
2. Sign-off R-U2: `proposed/Recon_6_stl.als` becomes `proposed/ultimate/Recon_6_u_stl.als` (this also brings in the rf fact you authorized for Recon_6_stl).
3. Sign-off R-U3 (the cores): `proposed/ultimate/Recon_6_u_core_ri.als` and `Recon_6_u_stl_core_ri.als` replace `proposed_twophase/Recon_6_core_ri.als` and `Recon_6_stl_core.als` as the Stage-1 families. They are mechanical (`derive_core.py --minimality ri`, re-checked byte-identical); if you approve 1 and 2, re-derive them from the applied files rather than copying.
4. Regenerate on cafe2 (simspect-c8; new workspace or new family names, because the old Recon_6 outputs are pre-fix): `partition_stage1.py <core> parts/<fam>` for both cores, then `launch_stage1.py --families Recon_6_u_core_ri Recon_6_u_stl_core_ri …`, then `launch_stage15.py --family Recon_6_u=Recon_6_u_core_ri:STAGE1_alloy/models/<Recon_6_u.als> --family Recon_6_u_stl=Recon_6_u_stl_core_ri:<…stl.als>`. Wipe or retire `out/Recon_6_core_ri`, `out/Recon_6_stl_core`, and any `testsets/Recon_6*` xml/llvm/asm/ann built from the old model (`--force` from `xml` for single-stage). Stage 2: `stl_bypass` mode for the stl family.
5. E6 (ruby3) gets the Recon_6_u testset; E2 (classic Recon-STT) gets the STT_6_u testset (F5).

SPT:
6. Sign-off S-U1: `SPT_6_oneLP_v3.als` becomes the SPT production model (copy `proposed/SPT_6_oneLP_v3.als` to `STAGE1_alloy/models/SPT_6_oneLP_v3.als`; update `specs/alloy_models.json` `canonical_models.SPT`; keep v2).
7. Regenerate single-stage: `python3 pipeline.py xml --model SPT_6_oneLP_v3 --config <SPT config with max_instances 300000> --force`, then llvm/asm with `--force` (or `make gen`). Retire cafe2's `out/SPT_6_oneLP_v2_core_ri` (v2, superseded, and capped at k4). Do not build an SPT two-stage family until DECIDE U-SPT-1 is settled.
8. Not to apply now: `SPT_6_u.als`, `SPT_6_u_core.als` (conservative core, not what the pipeline uses) and `SPT_6_u_core_ri.als` (new, RI, partition-checked).

Superseded once 1–7 are applied: `proposed/Recon_6_v2.als`, `proposed_twophase/Recon_6_v2_core_ri.als`, `proposed/Recon_6_stl.als`, `proposed_twophase/Recon_6_core_ri.als`, `Recon_6_stl_core.als`, `SPT_6_oneLP_v2_core_ri.als` (for new runs), and `blocks/Recon_6_u.block.als` unless SKELETON_u is adopted.

### Decisions for Anna (also in `URGENT_TODO.md`, ultimate-recon-spt)

- Approve Recon_6_u/Recon_6_u_stl (R-U1..R-U3). Recommendation: yes.
- SPT for the clean runs: (a) v3 single-stage (recommended), (b) wait for the SPT_6_u k4 count, conv check and parsexml InvOp, (c) v3 two-stage with k4 partitioned until exhausted.
- [u-8]: a store with an unresolved address does not conceal. Recommendation: keep (paper §4.5.2).
- A dedicated ReCon reveal-context corpus (g9 pin) for ReCon-specific tests. Recommendation: yes, for E6, after the Stage-2 re-load delay (B4/F1).
- Still open from the recovered report: reveal at LD2's commit (as built, recommended) or at its visibility point (model-fixes B1).

### Process note

Three runners from the stopped 3e17c539 session were still alive and waiting on the shared lock (`batch_u.sh list_final.tsv`, `recon/run_queries.sh RUNLIST_rest.tsv`, `run_spt_queries.sh ../SPT_6_u.als`); the 2026-11-09 "all agents stopped" note was wrong. Killing them was refused by the permission classifier, so they ran on and their results went to the same logs (the ReCon `fx_*` rows above come from the orphaned `RUNLIST_rest.tsv`). The orphaned `run_spt_queries.sh` (pid 44735) may still be waiting; its `EXIT` trap deletes the lock dir even when it never held it, so stop it with `kill -9`, not `kill`.

## ultimate STT family + SKELETON_u + jmp/RMW fanout (2026-11-09, ultimate-stt; resumes audit-fanout-1109)

All files below are NEW and unapproved; no existing `.als`, parsexml.py, gem5 build or checker was edited; no git writes. Alloy on the Mac under the shared mkdir lock (Java 17, symmetry 80, capped). Logs: `STAGE1_alloy/models/proposed/ultimate/queries/stt/runs.log` (STT) and `queries/runs.log` (skeleton). Note: three batches from the paused session were still alive (skeleton `batch_u.sh list_final.tsv`, two STT `runbatch_stt.sh` batches, plus waiting ReCon/SPT runners); I could not stop them (permission denied), so they ran to completion and their results are used below.

### Bottom line

- **STT_6_u.als is STT_6_v2.als.** Ignoring comments, the two files differ only by one helper `u_store_shadow_p` that nothing calls (`diff` with comments stripped). Same facts, preds and run lines, so the same instance set: equality holds by the text itself, which is stronger than an Alloy equivalence query. The derived core `STT_6_u_core_ri.als` likewise equals `proposed_twophase/STT_6_v2_core_ri.als` up to comments.
- **Recommendation for the clean runs: adopt the v2/u defense as the STT spectre model, under ONE name.** Use `STT_6_u.als` (it carries the cited defense block and the flavor notes) and retire `proposed/STT_6_v2.als` as a duplicate, or the reverse. Either way it is one sign-off: the instance-based protection set (model-fixes A).
- **The running cafe2 STT Stage-1 output stays valid.** The RI cores of STT_6 and STT_6_u are the same set: 129/129 at `but 3` and `but 4` (both exhausted; `q_core_u_core.als`), and canonically equal (80 distinct each, python canonicalizer over `c_STT_6_core_ri_b3.out` vs `c_STT_6_v2_core_ri_b3.out`). Only Stage 1.5 needs the new flat model.
- **STL flavor (`STT_6_u_stl.als`): not a drop-in replacement for the approved `STT_6_stl.als`.** It changes TWO things: the v2 protection set, and the true-alias fact (atom-based "every unresolved store has an aliasing younger load with no intervening store" instead of the rf-based `stl_alias_pair`). Its RI core count is **858** vs **306** for the approved STT_6_stl core (both exhausted at `but 3` and `but 4`). 858 is the same count as Recon_6_stl's atom-alias core. Needs its own DECIDE (below).
- **SKELETON_u: adopt later, not for these clean runs.** It is equivalent to STT_6's skeleton where checked, but the per-perturbation semantic equivalence checks time out, and adopting it means re-deriving every family at once.
- **jmp is already in the clean-run fanout, and it now has an end-to-end gem5 smoke.** simspect-c8's `runconfigs/twostage_fv2_20261109/stage2_STT_6_fv2.jsonc` uses `proposed/fv2_vocab.jsonc` (`jmp_direct: 0.5`). Not one cafe2 checkout's parsexml has `BRANCH_FORMS` yet, so that config must run from a checkout synced with the Mac's parsexml.

### 1. STT drafts: state and verification

| draft | what it is | verified (query → result) | verdict |
|---|---|---|---|
| `ultimate/STT_6_u.als` (529511a1) | STT_6 skeleton + 4-line Operand retype [u-1] + defense block: seed `(Loads & contract).inmem & o_p`, identity step, contract and leakage unchanged | text = STT_6_v2 (comment-stripped diff); `gen_lit_u` SAT; D2w (STT_6 instance that STT_6_u drops) **SAT** (`q_r_d2w.als`); M0 (old flags ⊆ new, no perturbation) **UNSAT** in 94 s; R-1 already shown for v2 (QR1a UNSAT → SAT, model-fixes A); 20 gained instances through parsexml → .ll → x86 .s without error, 19/20 keep the R-1 same-slot re-load | **adopt** (one name) |
| `ultimate/STT_6_u_core_ri.als` (29368a06) | `derive_core.py --minimality ri` of STT_6_u | = `STT_6_v2_core_ri.als`; 129/129 at but 3 and but 4, exhausted; set = STT_6_core_ri's (canonical, 80 distinct); `partition_stage1.py` → the same 10 partitions (kinds Branchxs, Loads) as STT_6_core_ri | **adopt**, but Stage 1 need not be re-run |
| `ultimate/STT_6_u_stl.als` (f08dad0c) | STL contract (store-address shadow) + v2 protection + atom-based alias fact + `u_stl_no_branch_speculation` | gen SAT; S1g (stale re-load shape) generated SAT; core 858 vs approved 306 | **hold**: alias DECIDE first |
| `ultimate/STT_6_u_stl_core_ri.als` (ebf94886) | its RI core | 858 at but 3 and but 4, exhausted (798 s) | follows STL DECIDE |
| `blocks/STT_6_u{,_stl}.block.als` | the same defenses written for SKELETON_u | assembled models gen SAT (`q_asm_sk`, `q_asm_stl_sk`); ported-vs-original counts at exactly 3: STT_6_u 80/80, Recon_6_u 80/80 | keep for SKELETON_u later |
| `ultimate/STT_6_rmw_u.als` (46f9f781) | RMW kind on the OLD location-based STT_6 defense (reported earlier) | see the RMW section above | **superseded in part**: if the RMW variant is ever built, rebase it on STT_6_u (seed `(Loads+Rmws) & contract`) |

- **Correction kept from the STT agent:** model-fixes said "STT_6 → v2 lost 0". D2w is SAT, so the lost set is not empty. The hand-built witness is a program in which old STT_6's location fold made a load look necessary (committed l1 reads A; the speculative chain l2 → st A → l4 re-reads A). Under instance-based taint, l4's own read is already a source, so that chain is not minimal. This is an artifact of the old model, not a lost leak.
- **Inconclusive:** `S1_same_flagged_old_STT_6_stl__UNSAT` came back SAT. The witness flags through a second load (pc2 reads the unresolved store's location), not through the S1 re-load, so the shape predicate is too loose to show anything. It neither confirms nor refutes the claim "old STL misses S1".
- **Not run (killed or timed out; not needed for the recommendation):** the STT agent's YRoT reference checks Y1-Y5, U2-U8, M1-M3, L1-L3 (`q_fast.als` timed out at 600 s after M0). They support its write-up (taint = YRoT union semantics) but do not change the decision.

**Defense-block diff, current canonical `STT_6.als` → `STT_6_u.als` (the three clauses):**

```
(1) speculation_contract_p   unchanged: uncommitted_p[p] & has_unresolved_brs_p[p]
(2) hardware_protection_policy:  fun ...: State {Mem_s}
                              →  fun ...[p]: Operand {(Loads & speculation_contract_p[p]).inmem & o_p[p]}
    prot_set_propagation_p:      s - (Loads & no_unresolved_brs_bf_or_is_p[p] & i).inmem.opstate
                              →  o            (identity: untaint is decided by the contract)
(3) leakage_function         unchanged: Loads.inaddr+(Branchxs).inreg
```

**Outside the defense block (skeleton, 4 lines, [u-1]):** `fun a` and `last_committed_protset_p` are retyped State → Operand; the seed call becomes `hardware_protection_policy[p]`; `secure_speculation_scheme_p` and `tag_xm` drop the `.(~opstate)` lift. These are the same 4 lines as the approved SPT_6_oneLP_v2 and the STT_6_v2 draft. The retype changes nothing by itself; it is what lets clause 2 name one load's read. Every STT-family model and core must take it together with the block.

### 2. SKELETON_u: state and verification

Results (`queries/runs.log`; scope `for 9 but 6` unless noted):

- **Holds:**
  - structural pieces equal STT_6's for every single perturbation: `q_struct_eq`, 0 counterexamples in 465 s;
  - leak predicate and tag equal with no perturbation: `q_sem_eq_nop`, 0 in 44 s;
  - changed facts equal except through 4-bit Int wrap: `q_facts_eq` gives 1 counterexample, `q_facts_eq_nobig` gives 0. STT_6 cannot hit the wrap at production scope: `q_overflow_stt6_facts` and `_gen` are both UNSAT at `for 9`;
  - counts at small exhaustive scopes: flat exactly 3, demo 80 = STT_6 80; RI cores demo 80 vs old 129 raw at but 3 and but 4. Old 129 raw is 80 distinct, and the demo keeps the idx symmetry break, so the counts agree;
  - Recon_6_u ported onto the skeleton: 80 = 80 at exactly 3. STT_6_u, Recon_6_u, SPT_6_u and STT_6_u_stl all assemble and generate.
- **Not proven:** `q_sem_eq_gen` timed out at 900 s; the per-family checks RR/RC/RS/RI were still running at write-up time.
- **Behaviour that differs by design:**
  - [sk-5]/[sk-6]: spo/rf bridging over several removed instructions (equal to STT_6 for one removal);
  - [sk-2]: idx is kept in cores, so core counts drop but sets do not;
  - [sk-3]: no `#` caps. At 12 operands, STT_6's caps wrap: `q_overflow_stt6_gen12` is SAT, the stage15-bound S3 bug. So SKELETON_u fixes a real bug, but only for resized (N > 6) Stage-1.5 models.
- **Relaxation facts measured:**
  - the commit boundary is always the unresolved gating branch (`q_rel_boundary` UNSAT);
  - no unresolved non-branch appears in generated instances (`q_rel_flags` UNSAT, so URGENT_TODO:76 has no duplicates);
  - RI, RO and RC-alone are not enforced in flat generation (SAT);
  - no RI-removed rf producer is shadowed by an older writer in cores (`q_ri_shadowed_writer_core` UNSAT);
  - unfed reads occur (`q_p5_unfed_flat` SAT; P5 is off by decision).
- **Recommendation: adopt later.**
  - It is the right long-term form: one skeleton, a lint against unperturbed reads (the SPT root cause), and a fold that does not depend on depth.
  - But adopting it changes every model's text at once, its multi-removal semantics differ by design, and its full equivalence is unproven.
  - For the clean runs use the minimal change: STT_6 skeleton + the 4-line retype.
  - Revisit when Stage 1.5 needs N > 6 (where [sk-3] matters).
  - `derive_core_u.py` and the port files stay as drafts. The port files and `demo_N8*` live only in the old session scratchpad; regenerate them with `derive_core_u.py assemble`.

### 3. Do the derived cores match what cafe2 expects?

- `STT_6_u_core_ri.als` and `STT_6_u_stl_core_ri.als` go through `proposed_twophase/partition_stage1.py` with the same 10 partitions as `STT_6_core_ri.als` (scope regex and one-line leakage_function found).
- Stage 1.5: the `stage_pipeline.py:60` needle `run gen_lit {\n  gen_useful_litmus\n}` occurs exactly once in `STT_6_u.als`, `STT_6_u_stl.als` and `STT_6_v2.als`.
- `stage_seed.py` reads no defense lines, so it is unaffected (it lacks only `TRmw`, which matters only for RMW models).
- simspect-c8's cafe2 Stage 1 (`/tests/simspect_alloy_20261108`, read about, not touched) runs `STT_6_core_ri`. Its output is reusable for STT_6_u because the core sets are equal.

### 4. Stage-2 smoke (scratch, deleted)

- **Mac, llvm:** 20 STT_6_u-only (R-1) instances from `STAGE3_gem5/triage/model_audit_20261108/queries/mf/t1_gained.out` went through `batch_generate.py` in both modes: 40/40 .ll and .ann.json.
- **cafe2, asm + gem5:** the same .ll went through `pipeline.py asm` with clang-15 (40/40) and `pipeline.py gem5`, on SpecLFB (E14 footprint config) and stt-master (E3 validation config). Result: 80/80 records `ok`, 0 errors.
- **Hits, default table:**
  - SpecLFB: 3/20 per mode (inst-000001/008/013), not triaged;
  - stt-master: 0/20. STT blocks the R-1 re-load, as the new model says it must.

### 5. jmp/RMW fanout plan (Anna 2026-11-09: jmps must be IN the clean-run fanout)

**Where it stands:**
- **J0 (exists, opt-in):** `branch_forms.jmp_direct` (parsexml `_load_branch_forms` :526, pass 5 :2555/:2950). A resolved, correctly-not-taken, non-transmitter branch is emitted as an inline-asm direct `jmp` to its fall-through, with probability p and its own per-test rng (crc32 `jmp:<stem>`), so other random choices do not move. No BTB annotation is written for it.
  - Roles: committed region (before the window) and speculative region: a resolved branch after the window-opening branch becomes a jmp that executes speculatively, which is the SpecLFB jmp-shadow position. Never the transmitter: a jmp has no operand any of our defenses treats as transmitting.
- **J1 (done, config only): jmp_direct is part of the proposed clean-run fanout.**
  - The clean-run config `runconfigs/twostage_fv2_20261109/stage2_STT_6_fv2.jsonc` already sets `paths.instruction_tables = STAGE2_compilation/instruction_tables/proposed/fv2_vocab.jsonc`, which has `"branch_forms": {"br_cmp": true, "jmp_direct": 0.5}`.
  - For the ReCon/SPT clean-run Stage-2 configs (not written yet), use the same table. It is general vocabulary: the branch roles come from the Alloy resolved flags, so it applies to every defense.
  - New `STAGE2_compilation/instruction_tables/proposed/jmp_all.jsonc`: the default table + `jmp_direct: 1.0`, for a jmp-pinned corpus.
- **J1 coverage (20 R-1 tests, Mac):** with `jmp_all`, 26/40 tests contain ≥1 litmus jmp (8 committed, 20 speculative). The other 14 have no resolved non-transmitter branch. With `fv2_vocab` (p = 0.5), 12/40.
- **J1 byte-identity:**
  - default table, run twice: identical;
  - default vs `jmp_direct: 0`: identical;
  - `fv2_vocab` with vs without `jmp_direct`: all 28 tests that get no jmp are byte-identical in .ll and .ann.json (ignoring the `branch_forms` key).
  - A config that does not enable jmp_direct is therefore unchanged.
- **J1 gem5 smoke (cafe2, scratch, deleted):** the 20 tests built with `jmp_all` (26/40 with an inline-asm jmp after clang-15) against the same 20 without:
  - SpecLFB: 0 errors; hits identical (3/20 per mode, the same stems);
  - stt-master: 0 errors; 0/20 hits in both.
  - So the jmp form compiles, annotates (BTB annotations skip the jmp pcs) and simulates on both a footprint build and a taint build, and on these tests it changes no verdict.

**Still to do:**
- **J2 (needs the parsexml owner):** a direct `call` form (`branch_forms.call_direct`). It is not cheap without a parsexml edit: the call pushes a return address (a store below rsp), so the emitter must keep the litmus frame out of the red zone and pop or adjust rsp. Proposal only.
- **J3 (the 35% with no resolved branch):** a fanout-v2 splice that inserts a `jmp 1f; 1:` at a chosen point (committed or speculative). This is a parsexml fanout_v2 hunk, so it is owner-gated. Until then, the pin (R3) keeps the tests that have one.
- **R1 (exists):** RMW as transmitter = the `STT_6_rmw` corpus (`make_rmw_corpus.py`, `orq $0`).
  - Before counting STT/ReCon hits on it, the check_ld multi-µop fix (DECIDE, RMW section 3.4) is needed. Alternatively, switch the rewrite to the register form with an explicit zero source: `OR_M_R` starts with `ldst`, so there is no `limm` artifact.
- **R2 (RMW off the transmitter):** speculative RMW on the secret's or transmitter's line (CleanupSpec E→M), committed RMW before the window, RMW as an STL source. The cheapest route needs no model change: a role-generalized `make_rmw_corpus` that rewrites a non-transmitter Alloy `ld` whose destination is dead into `orq %zero,(m)`, with the same gates and annotation re-resolution. R-1 shapes have exactly such dead committed loads (inst-000001 pc0).
  - Build it as a NEW `STAGE2_compilation/proposed/make_rmw_roles.py` that imports make_rmw_corpus. It is not built yet: it needs the cafe2 toolchain to smoke.
  - The model route is `STT_6_rmw_u` rebased on STT_6_u + Stage-1.5 (RJ-4 (b)).
- **R3 (the pin, done):** new `STAGE2_compilation/proposed/jmprmw_pin.py <testset dirs> --out census.json --pin-list stems.txt --link-dst <new testset>`.
  - It classifies every litmus instruction (inline asm only, so compiler glue jmps do not count) as jmp_direct / call_direct / rmw × committed / spec / xmit.
  - It writes a NEW symlink testset holding only tests with ≥1 jmp or RMW, which `testrun.py --model` can run as its own corpus.
  - Smoke: default table 0/40 pinned; `jmp_all` 26/40; an `orq $0` rewrite → `rmw@xmit`.
- **Which defenses run it:**
  - the jmp forms in the main fanout: every clean-run row;
  - the pinned jmp corpus: E14 SpecLFB (jmp-shadow) first, then E12a/b InvisiSpec, E13 CleanupSpec, E3 STT, E2 Recon-STT as controls;
  - the RMW corpora: E13 CleanupSpec warm and cold, E1 positive control, E3/E2 after the check_ld fix, E12a/b and E14 as controls. Not E11 SPT until an SPT block covers `Rmws`.
- **EVAL_MANIFEST:** not edited here; add a row when Anna picks the pinned-corpus option (DECIDE below).

### Apply for clean runs

**Sign-offs (one per `.als` change):**
- **S1:** approve `STAGE1_alloy/models/proposed/ultimate/STT_6_u.als` (529511a1) as the STT spectre model. It is the defense-block diff above + the 4-line [u-1] retype, and supersedes `proposed/STT_6_v2.als` (1ad8c5a9, identical semantics). Then copy it to `STAGE1_alloy/models/STT_6_u.als`; keep `STT_6.als` for old results.
- **S2:** approve `ultimate/STT_6_u_core_ri.als` (29368a06) as its Stage-1 core and copy it to `proposed_twophase/STT_6_u_core_ri.als`. Optional, because the cafe2 STT_6_core_ri output is reusable (equal set).
- **S3 (only after the STL DECIDE):** `ultimate/STT_6_u_stl.als` + `STT_6_u_stl_core_ri.als`, or an `STT_6_stl` variant with only the protection retype and the rf-based alias kept. I can write that as a new draft on request.
- No sign-off now for SKELETON_u, the blocks, or STT_6_rmw_u.

**Config keys for the clean runs (Stage-2 config of every family):**
- `"paths": {"instruction_tables": "STAGE2_compilation/instruction_tables/proposed/fv2_vocab.jsonc"}`, which carries `"branch_forms": {"br_cmp": true, "jmp_direct": 0.5}`;
- or, for jmp without the rest of fv2: `".../proposed/jmp_all.jsonc"` (`jmp_direct: 1.0`).
- Deploy the Mac's parsexml.py (with `BRANCH_FORMS`) to the cafe2 checkout that runs Stage 2 first. Today none of `/tests/simspect`, `/tests/simspect_fixed_20261030` or `/tests/simspect_alloy_20261108` has it.
- For a pinned jmp/RMW corpus: after asm, run `python3 STAGE2_compilation/proposed/jmprmw_pin.py testsets/<model> --out testsets/<model>_jmprmw.census.json --link-dst testsets/<model>_jmprmw`, then `testrun.py` on `<model>_jmprmw`.

**Regeneration (after S1):**
- **Stage 1:** reuse simspect-c8's STT_6_core_ri Stage-1 cores. Record in the manifest that they equal the STT_6_u core set (sha 29368a06 vs 47096ff7; proof above).
- **Stage 1.5:** flesh with `STT_6_u.als` as the flesh model (fresh output dir). The old flat STT_6 testsets are not regenerated in place.
- **Single-stage path instead:** `python3 pipeline.py xml --model STT_6_u --config <cfg> --force`, then `testsetgen.py` for llvm/asm. It is a new testset dir, so nothing to wipe.
- **Then:** llvm + asm with the clean-run Stage-2 config (wipe nothing old; new testset name). The Recon/SPT families follow the ultimate-recon-spt write-up.

### Decisions (also in URGENT_TODO)

- **U1:** adopt the STT_6_u/v2 defense (recommendation: yes, S1).
- **U2:** the STL alias fact. Options: atom-based (858 cores, matches parsexml pass2_6 pairing and the Recon/SPT STL drafts) or rf-based (306 cores, approved). Recommendation: atom-based, but measure first how many of the extra 552 cores concretize to a real alias under `stl_bypass`.
- **U5:** reuse the cafe2 STT Stage-1 output (recommendation: yes).
- **Pinned jmp/RMW corpus:** its own testset or only the fv2 p = 0.5 inside the main fanout. Recommendation: both, the pinned corpus as its own results row like C1.
- **SKELETON_u timing:** recommendation: later.

## ultimate (2026-11-09, audit-fanout-1109): ReCon — Recon_6_u

Drafts in `STAGE1_alloy/models/proposed/ultimate/` (Recon_6_u{,_stl}{,_core_ri}.als, blocks/Recon_6_u.block.als, queries/recon/); NEW files only, unapproved. Decisions in URGENT_TODO 'DECIDE (Recon_6_u'.

**Bottom line.** `Recon_6_u.als` is done and checked in Alloy. It is the STT agent's `STT_6_u.als` plus one ReCon change in defense clause 2:
- **Reveal:** once a direct load pair LD1 -> LD2 has committed, a later load's read of LD1's word is no longer a taint source.
- **Conceal:** a store to that word between LD1 and the later load cancels the reveal, unless the store's address is unresolved.

So `diff STT_6_u.als Recon_6_u.als` is a header paragraph, the block title, three functions and the seed line (13 code lines). The same holds for the STL flavor and the RI-only core. The three audit items are handled: R-1 by the shared instance-based STT seed, R-2 by the new reveal, and R-3 was already applied to `Recon_6.als` on 2026-11-09 with your authorization. Two exhaustive completeness checks timed out and are unresolved. No existing `.als`, `parsexml.py`, gem5, spec or paper file was touched, and there were no git writes.

**Files (all new drafts, unapproved), in `/Users/annaeaton/trippel/simspect/STAGE1_alloy/models/proposed/ultimate/`:**
- `Recon_6_u.als` (sha256 dba2d523): flat model, spectre (branch-only) flavor. Built on `STT_6_u.als` (529511a1).
- `Recon_6_u_stl.als` (625ae480): `STT_6_u_stl.als` (f08dad0c) plus the same change.
- `Recon_6_u_core_ri.als` (21d860df) and `Recon_6_u_stl_core_ri.als` (74081526): made with `proposed_twophase/derive_core.py --minimality ri`, the tool the STT agent used.
- `blocks/Recon_6_u.block.als` (e06a9cf8): the same block in the skeleton agent's `SKELETON_u.als` interface. It passes `derive_core_u.py lint`, and once assembled the skeleton is byte-identical to `SKELETON_u`.
- `queries/recon/`:
  - `make_recon_u.py` rebuilds every model file above with anchored exact-once edits;
  - `mk_queries.py` and `mk_ctx_queries.py` build the queries;
  - `run_queries.sh` is the lock-aware runner;
  - `show_inst.py` prints an instance as a program and tags its ReCon shape;
  - `runs.log` has every result; the query files are in `q/`.

**Recon_6.als working-tree change** (checked with read-only `git diff`). The only change is the 10-line `fact rf_from_most_recent_writer`, sha256 01252c82 -> 6f306195. You authorized it ("fix this pls, you have permission to do that line"), and main applied it with the hash-checked `apply_rf_fact.sh` (claudelog 2026-11-09; URGENT_TODO lines 39 and 43, DONE).

#### 1. How ReCon protects, unprotects and reveals

Sources read this session:
- ReCon paper: `~/Documents/quail/sources/papers/aimoniotis-2023-recon.pdf`. It is an ACM HTML print with no page numbers, so I cite sections.
- STT paper: `yu-2019-stt.pdf`, cited by page.
- gem5: the authors' tree `~/Downloads/dockerrecon/gem5-recon/src`. Line numbers on cafe2's `/work/gem5-recon*` run about 11-15 higher.

**What ReCon changes.** It is an optimization on top of STT or NDA. "The underlying secure mechanism maintains its entire threat model except for values that previously have been made public" (§3.1). It relaxes STT's notion of a secret ("speculatively accessed values that might be squashed") only for values already made public non-speculatively. Register values from before speculation were never secrets, and ReCon leaves that alone (§3.1).

**What is speculative.** This is STT's visibility point: in the Spectre model an instruction is safe once all older control-flow instructions have resolved (STT p5 §6.1). ReCon's evaluation uses "speculation cast by control flow and store instructions" (§3.1). In gem5, a load is speculative if it was decoded under a branch or store shadow (`decode.cc:686-694`), until every older shadow is freed (`shadow_tracker.cc` `freeSpecInsts`).

**What is protected.**
- STT: "If a load is unsafe, its output is always tainted" (STT p6 §6.2). Taint follows any tainted input, and a value is untainted when its youngest root of taint reaches the visibility point (STT p6, p9 §7.1).
- gem5 taints at rename (`rename.cc:717/719`) and keeps only the oldest tainted source (`taint_tracker.cc:108-131`). That second part is the known OTB bug, R-SA-8.
- Transmitters: a load with a tainted address is held (`lsq_unit.cc:2080`), and so is a branch with a tainted predicate (`inst_queue.cc:1453`).

**Reveal.** Only a direct-dependence load pair reveals, and only when LD2 commits:
- "pairs of dependent loads, in which the second address is entirely dependent on the output value of the first load ... marks this value as revealed when the second load commits" (§4.1);
- "RECON limits its detection to only the leakage of load pairs with a direct dependence" (§4.3);
- detection happens at commit, although LD2's visibility point would be the earliest secure point (§5.1).

The gem5 side of the pair table:
- at LD2's commit it checks LD2's sources src1, then src0, and sends one Reveal for the first match (`lsq_unit.cc:872-931`);
- LD1's entry is written at LD1's commit, unless LD1's own read was already revealed (`lsq_unit.cc:950-959`);
- a committing non-load clears its destination's entry (`commit.cc:1045-1050`).

Granularity is one bit per aligned 8-byte word (§5.2, §6.7).

**Conceal.**
- "Once an address is revealed, it is guaranteed to be safe as long as its contents do not change" (§4.4). A performed store conceals; store-to-load forwarding always delivers concealed data (§4.4.1-2, §5.2).
- gem5 clears the bit only at the store's start offset (`mem/cache/base.cc:1222`; R-SA-3), and never invalidates the pair table on a store (that is R-SA-2).

**When a revealed value may be used.**
- §5.4: "for STT, any load that receives a revealed value untaints its destination register".
- gem5: the reveal bit returns with the data (`base.cc:485`, `lsq_unit.cc:184`). `freeTaints` then clears the load's taints only if the load completed, its own sources are untainted and it was not store-forwarded (`taint_tracker.cc:143`).
- There is no retroactive reveal (`updateRevealedTaints` has no caller), so timing matters.
- A load that bypasses an unresolved store and reads the old, revealed value may be used (§4.5.2, Table 1 case 1).
- On classic caches the Reveal marks paddr 0, so ReCon behaves as Recon-STT (R-SA-1). On `/work/gem5-recon-ruby3` it marks the right word.

**R-1 really was wrong.** A merely non-speculative load of word A makes nothing public under STT (p6) or ReCon (§3.1, §4.1, §4.3). Treating it as public is SPT's value-level threat model, not STT's or ReCon's.

#### 2. Feedback from the logs, and how Recon_6_u handles it

- **R-1** (the location fold makes a word public): fixed by the shared STT seed and identity propagation (STT_6_u [u-4]/[u-5]). The audit's query QR1a goes from UNSAT on `Recon_6` to SAT.
- **R-2** (reveal clause is a no-op): replaced by [u-7].
- **R-3** (rf fact missing): already in `Recon_6.als`; inherited.
- **R-4** (store shadows): the spectre flavor stays branch-only. gem5 is then stricter, which adds no false positives. `Recon_6_u_stl.als` covers store speculation.
- **R-SA-1** (classic reveal dead): the model doesn't depend on the build. E2 (classic Recon-STT) should use the STT_6_u testset, and E6 (ruby3) the Recon_6_u testset.
- **R-SA-2** (stale reveal): a store between LD1 and LD2 conceals, and that shape is flagged (fb3), so tests that expose R-SA-2 are generated. B3 kept, as you decided.
- **R-SA-3/4/5/6** (byte, width, L2, Ruby holes): Alloy words are atomic, so these are not expressible.
- **R-SA-8** (OTB): the full gadget is flagged (fotb_full) and the hook point is generable (g5). This matches your 2026-10-30 decision that OTB comes from the second stage. The ReCon-amplified OTB needs 7 instructions, one more than the model allows, so it becomes a Stage-2 insertion (F3).
- **R-SA-10** (contract vs code differ): fixed. gem5 reveals only LD2's Base/Index source, which matches Stage 2's `movq (%probe_base,%idx,1)`.
- **R-SA-9/11/12/13/16-18:** gem5 bugs or out of scope; no model change needed.
- **B1:** reveal at commit is implemented (DECIDE 1). **B2:** see DECIDE 3. **B3:** kept. **B4:** a harness item (F1).
- **recon-ruby finding** (0 of 150,000 Recon_6 tests read a revealed slot speculatively): Recon_6_u generates the reveal-dependent shapes; F1 is needed to observe them.
- **Your decisions, followed:** RI-only Stage 1; OTB from the second stage; regenerate testsets only once the two-stage model exists; no cherry-picked minimality exemption in the model; no differential testing; diffs shown before approval.

#### 3. Changes from Recon_6.als (inline `-- [u-n]` tags)

[u-0] to [u-6] are the STT agent's tags in `STT_6_u.als`, inherited as written. [u-7] and [u-8] are mine. `Recon_6.als` is `STT_6.als` plus a no-op reveal plus `[p]` at the seed call, so this table covers every change.

| Tag | What | Why | Effect |
|---|---|---|---|
| [u-0], ReCon header | provenance (base sha256s) | | none |
| [u-1] | skeleton, 4 places: the protection set holds Operands, not States | per-instance protection can't be written over States | same form as the approved SPT v2 |
| [u-2], [u-3] | clause 1 unchanged (STT-Spectre); flavor selectors | STT p5 §6.1 | none |
| [u-4] | seed = the memory read of every speculative load | STT p6 §6.2; ReCon §3.1 | fixes R-1 |
| [u-5] | propagation = identity | R-1 | fixes R-1 |
| [u-6] | leakage function unchanged | STT §6.3/§6.4.1 | none |
| [u-7] | `recon_ld1_p` + `revealed_p`, subtracted from the seed | ReCon §4.1/4.3/5.1/5.2/5.4; `lsq_unit.cc:872-959`, `commit.cc:1045-1050`, `taint_tracker.cc:143` | fixes R-2/R-SA-10: in-flight-LD2 tests appear, true reveals drop out |
| [u-8] | `recon_concealer_p`: a store between LD1 and the re-load conceals, unless its address is unresolved | §4.4/4.4.1-2/5.2; §4.5.2 Table 1 case 1 | conceal shapes are flagged (the R-SA-2 tests); the exception changes nothing in the spectre flavor (g10) and avoids guaranteed false positives in STL (s2) |

One comment line differs without a tag ("// fun leakage_function" became "//fun", inherited from STT_6). Compared with model-fixes' `Recon_6_v2.als`, the code differs only by [u-8] and a refactor.

#### 4. Alloy evidence

All runs: `exactly 6` unless noted, Java 17. UNSAT means exhausted with 0 instances. Every run is a line in `queries/recon/runs.log`.

| Query | Asks | Result |
|---|---|---|
| g0 / s1 | `gen_lit` on Recon_6_u / Recon_6_u_stl | SAT: 20 in 3 s / 20 in 2 s |
| c1 | core at `but 3`, exhaustive | 129 in 6 s (same as Recon_6_v2 and the STT cores) |
| fa_true_reveal | committed pair on A; a speculative re-load of A is xm's only source; no store | UNSAT (not flagged). STT control SAT; STT generates it (g8 SAT) |
| fb1 / fb2 / fb3 | the same plus a committed store after LD2 / an in-flight store / a store between LD1 and LD2 | SAT / SAT / SAT (concealed) |
| fb4 | only an unresolved-address store in between | UNSAT ([u-8]); the v2 rule flags it (SAT) |
| fc / fd2 | LD1 -> ALU -> LD2 / LD2 not yet committed | SAT / SAT (flagged, no reveal) |
| fr1_qr1a | the audit's R-1 query | SAT (today's Recon_6: UNSAT, reproducing the audit) |
| fotb_full | full getOldestTaint gadget | SAT (flagged via the speculative source) |
| s2 / s3 (STL) | bypassing load reads the revealed old value / a committed store conceals it | UNSAT (STT_6_u_stl control SAT) / SAT |
| g1-g4 (with minimality) | in-flight LD2 at the commit boundary / R-1 / concealed reveal / ALU near miss | all SAT, 1-4 s |
| g5 | ALU with a blank second operand on the transmitter path (OTB hook point) | SAT |
| g10 | any generated instance with an unresolved store | UNSAT (77 s), so [u-8] changes no spectre test |
| d1 | Recon-useful, not STT-useful | 50 (cap); 50/50 in-flight-LD2 |
| d2 | STT-useful, not Recon-useful | 50 (cap); 50/50 true reveals |
| d3 | new vs old Recon_6 (gained) | 50 (cap); 50/50 R-1 shapes |
| g9 | flat generation plus a reveal-context pin | 100 in 5 s: 97 in-flight-LD2, 2 ALU near miss, 1 concealed |
| x1b (exploratory, on SKELETON_u) | context-minimal Stage-1 core (≤5 instructions) containing the pair | SAT, 3 in 20 s; one has the pair on its own register, so the pair is kept by context alone |
| fx_new_minus_old_not_r1 | facts only: every newly flagged transmitter is an R-1 witness | **unresolved** (timed out at 600 s) |
| fx_old_sub_new | facts only: whatever old Recon_6 flags, Recon_6_u flags | **unresolved** (timed out at 900 s; run once, as asked) |

Both completeness claims hold by reading: any word the pair reveals was read by LD1 non-speculatively, so the old fold had already made it public. The d3 sample (50/50 R-1) agrees. Skipped to save time: the lost-vs-old sample, extra OTB variants, and the context-minimality UNSAT controls.

**Lock incident.** At 01:48:51 another agent's `mkdir` of the lock succeeded while my query held it, which means someone had removed the lock directory mid-run. For about 3 minutes two Javas ran at once. I stopped my side, and my runner now also waits until no other `a6Count` Java is running before taking the lock. The `mkdir` lock has no owner check; an owner file or `flock` would close this gap.

#### 5. Skeleton issues (for the skeleton agent)

1. [u-1] is a skeleton change. It is needed by STT, ReCon and SPT alike, and SKELETON_u [sk-7] makes the same change.
2. `STT_6`'s `spo_p` and `fix_rf_hole_p` bridge only one removed instruction, so double perturbations are inexact there. SKELETON_u [sk-5]/[sk-6] fix this, which is why I ran x1b on SKELETON_u.
3. False positive in the `derive_core_u.py` lint: `\bInstruction\s*-` also matches the arrow in `Instruction -> Instruction`. Suggested fix: `\bInstruction\s*-(?!>)`. I worked around it.
4. The 7-deep fold is moot under identity propagation; [sk-8] replaces it anyway.
5. `tag_xm` is a fact, so it restricts facts-only queries. That is harmless for the checks here.

#### 6. DECIDE items (nothing applied; each needs your sign-off)

- **DECIDE 1 (B1): reveal at LD2's commit or at its visibility point?**
  - (a) Commit (implemented). This is what ReCon specifies (§5.1) and what gem5 does. In-flight-LD2 tests count as leaks the defense must block.
  - (b) Visibility point, the paper's security bound. It is a one-line change, and the in-flight-LD2 tests disappear.
  - Recommendation: (a). Label any such hit "early reveal" in triage.
- **DECIDE 2 ([u-8]): does a store with an unresolved address conceal?**
  - (a) No (implemented): the re-load may bypass it and read the revealed old value (§4.5.2 case 1).
  - (b) Yes, any store conceals (v2's rule).
  - The two give the same spectre testset (g10). In STL, (b) makes the s2 shape a guaranteed false positive on a working ReCon.
  - Recommendation: (a).
- **DECIDE 3 (B2): how do ReCon-specific tests reach the two-stage corpus?** Plain RI cores never contain the pair.
  - (a) Stage 1.5 with the flat Recon_6_u: it keeps the shapes (g1, g3, g4 SAT), but rarely.
  - (b) A dedicated corpus with the reveal-context pin. The g9 sample is 97% in-flight-LD2, so partition by sub-shape to balance it.
  - (c) Context ("second-order") minimality: keep an element if removing it alongside a necessary perturbation makes the instance insecure again. It equals plain minimality for STT, keeps un-protect near misses (ReCon reveals, SPT declassification), and x1b found such cores. It is a minimality-rule (skeleton) change.
  - (d) Accept ReCon = STT in Stage 1.
  - Recommendation: (b) now, and (c) as the "cleverer minimality" you asked for.
- **DECIDE 4: approve Recon_6_u?** It is STT_6_u + [u-7]/[u-8], so it depends on approving STT_6_u. The alternative is model-fixes' Recon_6_v2. Recommendation: approve both, so the two models stay one diff apart.
- **DECIDE 5 (F1): build the Stage-2 re-load delay for E6?** Recommendation: yes, with a true-reveal positive control.
- **DECIDE 6 (F2): probe aliasing on E6.** Options: (a) a Stage-2 load-separation option, (b) a diagnostic bucket, (c) both. Recommendation: (c), with the bucket first.

#### 7. Stage-2 / harness follow-ups (owners needed; none done)

- **F1 (blocks any ReCon signal).** The speculative re-load must reach the cache after LD2 commits. In one-pass timing the transmitter runs before LD2 retires (recon-ruby: tick 3040000 vs 3042000), and gem5 has no retroactive reveal.
  - Options: (a) Stage 2 delays the re-load's address with a slow, untainted chain; (b) a hook that holds window loads until the last committed instruction retires.
  - Validation: a true-reveal test (from the d2 set) should show `allowlistedTaintsFromTT > 0` on ruby3.
- **F2 (new, by reading; possible false positives on E6).** A load with a specified address is emitted as `movq (%probe_base,%secret,1)` (`parsexml.py:2626-2642`), and all memory and registers start at zero (`:2247-2268`), so every such load reads `probe_mem[0]`. On ruby3, a committed pair whose LD1 uses a probe address therefore reveals `probe_mem[0]` for every later probe-addressed load, even when Alloy gave them different words. ReCon would then legitimately release a re-load the model flags. This is the ReCon version of the A2 aliasing artifact.
- **F3.** A fanout_v2.otb variant that inserts a revealed re-load as the older merge source (the ReCon-amplified OTB, R-SA-8).
- **F4.** The audit's fanout rule 12 becomes live on ruby3: no inserted pre-window load may form a direct pair with an Alloy load's destination register.
- **F5.** E6 must use the Recon_6_u testset. STT's true-reveal tests are legitimate releases on a working ReCon.
- **F6.** `cache_setup: cold` must stay prologue-only for ReCon tests, because a flush erases reveal bits (§5.2).

**Pending decisions in one place:** DECIDE 1-6 above. They are not yet in `URGENT_TODO.md`; my brief said not to write `.md` files.

## ultimate (2026-11-09, audit-fanout-1109): STT — STT_6_u

Drafts in `STAGE1_alloy/models/proposed/ultimate/` (STT_6_u{,_stl}{,_core_ri}.als, blocks/STT_6_u*.block.als, queries/stt/); NEW files only, unapproved. Decisions in URGENT_TODO 'DECIDE (STT_6_u'.

**Bottom line.** I wrote `STAGE1_alloy/models/proposed/ultimate/STT_6_u.als`. Its active semantics are the same as the model-fixes draft STT_6_v2. Taint starts at the memory read of every unsafe load. It spreads forward along every rf/ddi edge. Untaint comes from the contract itself: there is no program-order fold, no declassification and no reveal. This matches the STT paper and the gem5 code. Around it I added a fully cited three-clause defense block, flavor selector lines, an RI-only core, an STL flavor with its own core, and the same block in the skeleton agent's SKELETON_u format. No existing file was edited, there were no git writes and I wrote no md files.

Three things are new:
- **"Lost 0" was wrong.** The model-fixes claim that STT_6 → v2 loses no instances does not hold. The lost set is non-empty (Alloy witness, confirmed independently in Python), but every lost instance is a minimality artifact of the old location-based fold.
- **Stage 1 can be reused.** The Stage-1 RI core sets of STT_6 and STT_6_u are provably identical (129 = 129, exhausted at ≤3 and ≤4 instructions). Only Stage 1.5 needs the new model.
- **One skeleton-level gap remains.** The model under-taints relative to STT when an instance has an unsafe load with no Inmem, or omits its optional Inmem→Outreg ddi edge. This happens in generated instances too, but it only ever means the concrete program carries more taint than the model, never less.

### (1) How STT protects and unprotects

Sources read this session: `~/Documents/quail/sources/papers/yu-2019-stt.pdf` (PDF page numbers below) and `~/trippel/defense_src/stt_e3283b9/src` (= `/work/stt`). `/work/stt-master` (5bf4110) differs only in `iew_impl.hh` (the 18e304f pending-squash fix).

**What is speculative.**
- Loads are the access instructions. An access is *unsafe* until it reaches its visibility point (VP). VPs are reached in fetch order (p5 §6.1).
- Spectre model: "an instruction has reached the visibility point if all older control-flow instructions have resolved". Futuristic model: only once it "cannot be squashed" (p5).
- gem5: `ROB::updateVisibleState` clears `prevBrsResolved` at the first control instruction that is not `readyToCommit`, faulted or squashed (`cpu/o3/rob_impl.hh:489-495`). It then sets `isUnsquashable` to `isPrevBrsResolved` in Spectre mode, or `isPrevInstsCompleted` in Futuristic mode (`:518-520`).
- In STT-Spectre, store-address and memory-dependence speculation are implicit branches to protect (p8 §6.4.2), not VP sources.
- Recon-STT is different. Its decode turns every conditional branch and every store into a shadow caster, and every load decoded under a shadow into a speculative instruction (`gem5-recon/src/cpu/o3/decode.cc:685-695`, checked in `~/Downloads/dockerrecon`). A store's shadow ends when its address is valid (`secure_scheme/shadow_tracker.cc:228-235`).

**What is tainted.**
- "STT taints the output of any speculative access instruction" (p5).
- gem5: `isAccess()` is `isLoad()` (`cpu/base_dyn_inst.hh:675`), and `compute_taint` marks the output of an access that is not unsquashable as tainted (`rob_impl.hh:812-813`).

**How taint spreads.**
- "an instruction's output register is tainted if any of its input registers are tainted" (p6 §6.2). That is union semantics with no GLIFT-style precision.
- gem5: `explicit_flow` taints an instruction when any of its uncommitted producers has a tainted output (`rob_impl.hh:709-724`), and the output is tainted exactly when the inputs are (`:809-811`).
- No taint is kept in memory or across store-to-load forwarding: "If a load is unsafe, its output is always tainted. If a load is safe, every instruction on which it depends has also reached its visibility point" (p6).

**How it unprotects.**
- Untaint is automatic: "When an access instruction becomes safe, its output register is untainted … when all the data dependencies of an instruction become untainted, the instruction's output is untainted" (p6).
- The hardware tracks the Youngest Root of Taint (YRoT). It waits "for the youngest access instruction that is causing the taint for i to reach the visibility point" (p9 §7.1), and "instr i can execute = yrot_i < VP" (p10 §7.3).
- gem5 instead recomputes all taint every commit cycle (`commit_impl.hh:1596`), which gives the same result.
- STT has no declassification and no reveal.
- Because VPs are reached in order, "the YRoT has passed the VP" is the same as "no load in the value's backward data cone is unsafe". That is why the Alloy snapshot needs no fold at all.

**What transmits.**
- Explicit channel: a load's address. Paper: "Classifying only loads as transmitters will block memory system-related explicit covert channels" (p5); for loads, delaying execution "implies delaying the TLB lookup" (p6 fn 2). gem5: `isTransmit()` is `isLoad()` (`base_dyn_inst.hh:676`), held back by `fenceDelay(isArgsTainted())` (`lsq_unit_impl.hh:1013`).
- Integer and FP divide become transmitters only with `moreTransmitInsts` 1 or 2 (`base_dyn_inst_impl.hh:275-294`); ours is 0. Stores are assumed to perform at retirement (p5).
- Implicit channel: branches. Predictors are updated only with untainted data, and "the effects of branch resolution" are delayed "until the branch's predicate becomes untainted" (p7 §6.4). "It is safe to resolve a branch as soon as its predicate becomes untainted, even if an older branch with a tainted predicate has not yet resolved" (p7 §6.4.1). gem5: a pending squash (`commit_impl.hh:934-952`) and a deferred predictor update (`fetch_impl.hh:1021`).
- Implicit branches: store-to-load forwarding and memory-dependence speculation (p8 §6.4.2), with the §6.5 optimization "we issue the load unconditionally" (p9; `lsq_unit.hh:735-760`).
- Store-address channels are outside our contract (Anna, 2026-11-08).

**How the model encodes it (STT_6_u).**
- Clause 1 (what is speculative): the Spectre VP. It records your rule that an executed branch with a pending squash counts as unresolved.
- Clause 2 (protection set): sources are the Inmem of every unsafe load. Propagation is the skeleton's `^op_edges` closure. The per-instruction step is the identity.
- Clause 3 (leakage function): load addresses plus the predicates of transmitting branches.

### (2) Feedback absorbed

| Item (source) | How STT_6_u handles it | Status |
|---|---|---|
| R-1 = STT-3 = Recon F2: the location-based fold never flags a speculative re-load of a word a non-speculative load already read (MODEL_AUDIT_SPT_RECON; QR1a was UNSAT) | Instance-based taint via [u-1], [u-4], [u-5]. Re-load flagged: U1 SAT; old model: UNSAT | done; your approval (U1 below) |
| model-fixes A/A1: STT_6_v2 and the State→Operand retype (URGENT_TODO:40,44) | Same semantics. The four-line retype is identical to the approved SPT_6_oneLP_v2 and to SKELETON_u [sk-7] | done; your approval |
| model-fixes "lost 0/3000; t1_lost found none in 1500 s" | **Corrected**: lost is non-empty (D2w, Python cross-check), and every lost instance is a location artifact (proof below) | correction |
| A2: `rf_from_most_recent_writer` | Already in the STT_6 skeleton; kept | done |
| A1: source-derived taint / constant-address false positives | STT taint is already source-derived. U5 UNSAT: an ALU on committed values is never tainted. Note: §A1's "safe/committed is not a valid untaint reason" is SPT-only; for STT it *is* the untaint rule | done |
| P5 unfed reads | Skeleton issue SK3. For STT they can only under-taint | not in the defense (skeleton) |
| Post-hoc checker trap: the fold covers only 7 positions | The step is the identity, so STT_6_u does not depend on the fold or on program length | solved by construction |
| Glossary (7), "protection set as updated by the most recently committed instruction" | Moot for STT (no fold); the paper wording is yours | wording is yours |
| RR flags on non-branches may create duplicates (URGENT_TODO:76) | L1 UNSAT: no non-branch is ever unresolved in a generated STT instance | answered |
| DESIGN.md invariant "the xm branch is always resolved" | L3 UNSAT: it follows from the contract plus tag_xm | answered |
| S1 xmm4 taint skip | A gem5 bug; `Reg_s` is class-agnostic and the FP corpus covers it | not in the model (vocabulary) |
| S4 one-cycle window | The contract already flags S4's transmitter (B1 unresolved under your rule). Only the trigger context is pruned (L2). You ruled out minimality exemptions, so a Stage-2 splice is proposed (section 7) | not in the defense |
| A3c hidden younger squash | Same structure; detection blocked by your no-differential-testing rule | not in the defense |
| A4, and "executed but not squashed = unresolved" | Clause 1 follows the paper; your rule is recorded in a comment | done |
| S2/S3/KV3 store-address leaks do not count (you, 2026-11-08) | Store addresses are excluded from the leakage function; the paper alternative is written next to it | done (decided) |
| STT-1, store as implicit branch | As a speculation source: the stl flavor. As a transmitter: out by your decision | done |
| STT-2, mispredicted xm branch | Stage 2 already forces every xm branch to mispredict; the model keeps it resolved | no change needed |
| STT_6_shadows and its true-alias fact (URGENT_TODO:130-131) | Shadows selector documented. Under full minimality every instance has one source, so shadows = spectre ∪ stl. The stl flavor uses the atom-based alias | your call (U2, U3) |
| Futuristic (parked) | Selector line only | not built |
| moreTransmitInsts / other_x | Alternative leakage line written; TOtherx behaves exactly like TOthern under STT | your call (U6) |
| OTB (Recon-STT getOldestTaint) | U3 SAT: a value merged from a safe and an unsafe load stays tainted (youngest-root semantics). U3b UNSAT: a safe-only merge is untainted. Generation stays with the fanout-v2 OTB splice | done (semantics) |
| Two-stage, RI-only cores | Core derived mechanically; the core set equals STT_6's (proof and counts) | your call (U5) |
| Unsafe load with no Inmem is not a source ("kept on purpose") | Kept; the gap is now shown exactly (Y3, Y4, Y5g) | your call (U4) |
| ReCon agent | `Recon_6_u.als` is built on STT_6_u (sha256 529511a1) | consistent |
| RMW agent | `proposed/ultimate/STT_6_rmw_u.als` still uses the old location-based defense (`hardware_protection_policy: State {Mem_s}`) | needs to adopt the STT_6_u block |

### (3) The [u-n] changes vs STT_6.als (sha256 7a6ac4c0…)

| Tag | Where | Change | Why | Effect |
|---|---|---|---|---|
| u-0 | header | provenance and an index of the changes | review | none |
| u-1 | skeleton, 4 places: `fun a`, `last_committed_protset_p` (signature and seed call), `secure_speculation_scheme_p`, `tag_xm` | the protection set holds Operands; the `.(~opstate)` lift is dropped | a set of States cannot protect one load's read of word A without protecting every operand on A, which is R-1 | identical to SPT v2 and SKELETON_u [sk-7]; no effect on its own |
| u-2 | clause 1 | Spectre contract unchanged from STT_6.als:325; helper `u_store_shadow_p`; one-line selectors written out for stl, shadows and futuristic | paper p5; `rob_impl.hh:489-495, 518-520`; recon `decode.cc:685-695` | none for spectre |
| u-3 | flavor facts | spectre: none. stl: no branch speculation, plus an atom-based true alias (the same pairing `parsexml` pass2_6 uses) | generation side conditions of the STL primitive | stl only |
| u-4 | clause 2 seed | `Mem_s` → `(Loads & speculation_contract_p[p]).inmem & o_p[p]` | p5 and p6 quotes above; `rob_impl.hh:812-813` | gains the R-1 shapes, loses only artifacts |
| u-5 | clause 2 step | location removal → identity | untaint is decided by the contract (YRoT, p9) | fold-free |
| u-6 | clause 3 | unchanged; two alternatives documented (`+Stores.inaddr` for paper §6.4.2, out by your decision; `+Otherxs.inreg` for moreTransmitInsts ≥ 1) | `isTransmit()` is `isLoad()`; our configs use moreTransmitInsts=0 | none |

### (4) Alloy evidence

Setup: Mac, Java 17, SAT4J, symmetry 80, shared lock. All commands of a file run in one JVM via `proposed/ultimate/queries/a6RunAll`. Results are in `queries/stt/runs.log`, witnesses in `queries/stt/<q>.out/`. Scope is `for 9 but exactly 6 Instruction` unless noted. Facts-only queries run on copies where `fact tag_xm` is demoted to a predicate, so they range over every program.

- **The model is satisfiable.** `gen_lit` is SAT for STT_6_u (0.7 s) and STT_6_u_stl (0.85 s). The SKELETON_u-assembled blocks are SAT for flat, R-1 and core (≤3) runs in both flavors (0.6–2.5 s).
- **Hand-built unprotect shapes (`q_u`, all 15 as expected; SAT 0.06–0.25 s, UNSAT 0.2–4.4 s):**
  - Speculative re-load of a committed word is flagged (U1 SAT); the old model does not flag it (UNSAT).
  - A safe but uncommitted load (after a resolved branch, before the unresolved one) is untainted (U2 UNSAT); the same load after the unresolved branch is tainted (U2c SAT).
  - Union / youngest root: a merge of a safe and an unsafe load is tainted (U3 SAT); a merge of safe loads only is not (U3b UNSAT).
  - A value forwarded from a committed store with no data source is still tainted (U4 SAT).
  - An ALU fed only by committed values is untainted (U5 UNSAT).
  - A br_x predicate from an unsafe load is flagged (U7 SAT); from committed values it is not (U7b UNSAT).
  - A tainted store address does not make the program insecure (U8 SAT).
  - Each UNSAT shape has a SAT existence control (X2, X3, X5, X7).
- **STL flavor.**
  - A stale read of a committed word by the bypassing load is flagged by STT_6_u_stl (SAT 0.16 s), not by the old STT_6_stl defense (UNSAT 0.7 s), and the shape exists (SAT).
  - The same shape is generated under the generator (S1g SAT).
  - My first version of this shape omitted "no store forwards into the bypassing load" and came back SAT on the old model through a second taint path, an older unresolved store's forwarded data. It is superseded.
- **Structure of the flat generator (`q_gen`).** L1 UNSAT (24 s): no non-branch is unresolved. L2 UNSAT (82 s): the only unresolved instruction is the first uncommitted one. L3 UNSAT (1.5 s): the xm branch is resolved. L4 SAT: committed loads do occur. The R-1, STL-forward and br_x shapes are all generated (SAT, < 0.2 s each).
- **Differential vs STT_6.**
  - M0 UNSAT (94 s): everything the old model flags, STT_6_u flags too (at the unperturbed program).
  - D2w SAT (1.1 s): a lost instance, hand-built from the argument. Program order: committed `ld [A]`; unresolved branch; `r1 ← ld [M]`; `st r1 → [A]`; `r2 ← ld [A]` (forwarded); xm = `ld [r2]`. The old model needs M only because the committed load had made A public. In STT_6_u, the re-load of A is a source on its own.
  - Proof that this is the only kind of loss: anything the old model flags starts at an operand on a word no non-speculative load reads. That operand is an unsafe load's Inmem, or a store's Outmem whose only out-edge is rf into such an Inmem. So STT_6_u flags it too, under every perturbation (old ⊆ u). Hence a gained instance always has an R-1 witness on xm, and a lost instance always has an R-1 witness under some removal of a state (RS perturbation).
  - Not finished within the caps: M1–M3 (old ⊆ u under the other perturbations) and my gained-completeness query D1 (stopped after ~13 min). The identical-semantics `t1_gained_complete` from model-fixes is UNSAT in 68 s.
- **Independent cross-check** with the model-fixes Python re-implementation (`mf_semantics.py`):
  - First 30 STT_6_u instances: 30/30 accepted under the new semantics, 28 also under the old, 2 gained.
  - 30 forced R-1 instances: 30/30 accepted under the new semantics, 0/30 under the old.
  - D2w witness: accepted under the old semantics, rejected under the new ("RS->Mem_s$0 not necessary").
- **Cores.**
  - STT_6_u_core_ri: 129 cores at ≤3 and at ≤4 instructions (exhausted, 3 s / 34 s). This equals STT_6_core_ri, STT_6_v2_core_ri and the cafe2 STT Stage 1 (129, all with 3 instructions).
  - Why the sets are equal: neither model can make a non-speculative instruction RI-necessary, and the boundary is the only unresolved branch. So no core contains an R-1 witness, and both defenses flag the same operands under every perturbation.
  - STT_6_u_stl_core_ri: 858 cores at ≤3 and ≤4, against 306 for the approved STT_6_stl_core. The difference is the alias fact (atom-based vs rf-based); cafe2's Recon_6_stl, which also uses the atom alias, also has 858.
- **YRoT equivalence.** Y3 SAT and Y4 SAT show exactly where the model under-taints: an unsafe load with no Inmem, or without its Inmem→Outreg ddi edge. Y5g SAT (1.3 s) shows this also happens in generated instances: `B; r0 ← ld [M0]` with no ddi edge; `st r0 → [M0]`; `r ← ld [M0]`; `br_x r` = xm. Here xm is flagged through the second load's own read, so the verdict is unchanged. The UNSAT proofs Y1/Y2/Y2b (the model flags exactly what YRoT taints, given the preconditions) did not finish within 10 minutes; the U shapes cover the concrete behaviours.
- **Stage-2 smoke test.** `batch_generate.py` on 120 dumped instances (30 flat spectre, 30 R-1, 30 stl, 30 stl-S1) produced `.ll` and `.ann.json` for 120/120, both branch modes, `stl_bypass` for STL, 0 errors. In the first R-1 test the committed load and the speculative re-load both read `0(%mem_base)`, and the transmitter is `movq (%probe,%r11,1)`.
- **Lock incident (mine).** At about 01:48 I `rmdir`'d the shared lock right after another agent had taken it. Until about 01:52, two javas ran at once on the Mac, so other agents' run times in that window may be inflated. I started a guard that would restore the lock; it never had to act, and nothing of mine is still running. Separately, `q_r_d2w`, `q_r_stl_gen` and two core counts in my directory were run by another session during my interruption; their results are in `runs.log`.

### (5) Skeleton issues (for the skeleton agent)

- **SK1.** Per-instance taint needs an Operand-typed protection set. That is my [u-1], which equals SKELETON_u [sk-7]. The plug-in blocks are `blocks/STT_6_u.block.als` and `blocks/STT_6_u_stl.block.als` (lint 0 errors / 0 warnings; `derive_core_u.py check` reports byte-identical outside the slot).
- **SK2 (new).** ddi edges are optional in the skeleton, but STT, gem5 and Stage 2 all propagate from every input to every output, and a load's output is always tainted when the load is unsafe. Shown by Y4 and Y5g. Options:
  - (a) a vocabulary fact making the load Inmem→Outreg edge and every ALU Inreg→Outreg edge mandatory. This is closest to STT, gem5 and Stage 2, and removes instances that differ only in optional edges; check SPT's untaint rules first.
  - (b) keep ddi optional, and have the post-hoc graph builder add all those edges.
- **SK3.** Unfed reads (P5): for STT, an unfed read only means the concrete program carries more taint than the instance.
- **SK4.** STT needs no fold. `last_committed_protset_p` is a misnomer.
- **SK5.** The structure lemmas L1–L3 mean minimality can never keep context that only matters for when an implementation acts: S4's older resolved branch and its load, A3c's younger branch, OTB's second root, and in cores the R-1 committed load. Put that context in Stage-1.5 pins or Stage-2 splices validated by the post-hoc checker, not in minimality.
- **SK6.** Under STT, TOtherx is identical to TOthern, and TBranchx differs from TBranchn only in being scored.
- **SK7.** SKELETON_u's lint also rejects raw flags inside generation facts. The STL facts therefore use `[no_p]` forms.
- **SK8.** Core counts from `derive_core.py` (idx stripped) and from SKELETON_u (idx kept) are not comparable as numbers; compare sets.
- **SK9.** `tag_xm` being a fact silently narrows facts-only queries to programs whose xm is flagged.

### (6) Decisions for you (my recommendation is marked)

- **U1. Adopt the STT_6_u defense, with the Operand skeleton, for the STT-family two-stage regeneration?**
  - (a) Adopt. This adds the R-1 tests (about 3.8% of a 3000-instance sample) and drops only artifact instances.
  - (b) Keep STT_6 and state the R-1 scope limit in the paper.
  - (c) Defer.
  - **Recommendation: (a).**
- **U2. STL alias fact: atom-based or rf-based?**
  - (a) atom-based, as in `STT_6_u_stl`: the true alias is a shared `Mem_s` atom, and no rf edge from the store is required.
  - (b) rf-based, as in the approved STT_6_stl: the store must rf-feed the aliasing load.
  - Atom-based is a superset of rf-based and is how parsexml pairs store and load. It gives 858 cores instead of 306. If you choose it, the STT_6_stl Stage 1/1.5 output (266,946 instances from 306 cores) must be regenerated.
  - **Recommendation: (a), atom-based.**
- **U3. What stimulus for E2 (Recon-STT)?**
  - (a) Two corpora: STT_6_u plus STT_6_u_stl.
  - (b) A combined shadows model (the same set under full minimality).
  - (c) STT_6_u only, which never tests store shadows.
  - **Recommendation: (a).**
- **U4. An unsafe load with no Inmem (or no Inmem→Outreg edge) is not a taint source.**
  - (a) Keep it: the secret is defined as a memory word, and RS-minimality keeps that word.
  - (b) Seed such a load's Outreg instead. Removing a word would then never secure a load, minimality would prefer loads without Inmem, and the same-word shapes like R-1 would disappear.
  - **Recommendation: (a), together with SK2 (a).**
- **U5. Reuse the cafe2 STT Stage-1 output?** The core sets are provably identical.
  - (a) Reuse it and re-run only Stage 1.5, from STT_6_u.
  - (b) Re-run Stage 1 from STT_6_u_core_ri for clean provenance.
  - **Recommendation: (a)**, recording the proof and the core-file hashes in the manifest.
- **U6 (lower priority). TOtherx duplicates TOthern under STT.**
  - (a) Keep it.
  - (b) Forbid Otherx in STT-family generation.
  - (c) Make other_x a transmitter only in a moreTransmitInsts ≥ 1 run.
  - **Recommendation: (a)**, revisit if the Stage-1.5 volume is too large.

### (7) Stage-2 / parsexml / harness follow-ups

- **Nothing blocks the spectre flavor.** The vocabulary is unchanged. The `stage_pipeline.py` needle is present, `derive_core.py` worked unchanged, and the smoke test was 120/120.
- **Stage 1.5 must use STT_6_u.als as the flesh model.** The R-1 shapes can appear only in Stage 1.5, because RI removes the committed load from cores.
- **Post-hoc checker:** use STT_6_u as the STT reference, since it is fold-free. Its builder should give every real load an Inmem and add every input→output ddi edge (SK2).
- **S4 without a model exemption.** Proposal only: a Stage-2 context splice in front of the window-opening branch. It would add a correctly predicted branch B0 with a resolve stall, then a load L1, and make the window-opening branch read L1 (`branch_cond.from_alloy`, already opt-in). The post-hoc check confirms the leak condition is unchanged; this needs the per-branch stall knob.
- **STL flavor:** concretize with `stl_bypass`. It runs only on `/work/gem5-recon-stl`, which is stale (the existing rebuild decision).
- **After approval, record the hashes** (main or you) in `specs/defense_units.json` and `EVAL_MANIFEST`:
  - STT_6_u: 529511a1…
  - STT_6_u_stl: f08dad0c…
  - STT_6_u_core_ri: 29368a06…
  - STT_6_u_stl_core_ri: ebf94886…
- **RMW agent:** `STT_6_rmw_u.als` should adopt the STT_6_u block.

### Files

All under `/Users/annaeaton/trippel/simspect/STAGE1_alloy/models/proposed/ultimate/`:
- `STT_6_u.als`
- `STT_6_u_stl.als`
- `STT_6_u_core_ri.als`
- `STT_6_u_stl_core_ri.als`
- `blocks/STT_6_u.block.als`
- `blocks/STT_6_u_stl.block.als`
- `queries/stt/`: the generators `make_stt_u.py`, `make_queries_stt.py` and `make_dump_stt.py`; the runners `runbatch_stt.sh`, `rundump_stt.sh` and `runall_stt.sh`; `crosscheck_stt.sh`, `stage2_smoke_stt.sh`, `summarize_stt.py`, `a6DumpAll.java`; and `runs.log` plus the `.out/` witness directories. These go to the next `make sync` when you run it.

## ultimate (2026-11-09, audit-fanout-1109): shared skeleton — SKELETON_u

Drafts in `STAGE1_alloy/models/proposed/ultimate/` (SKELETON_u.als, blocks/, STT_6_skel_demo{,_core_ri}.als, derive_core_u.py, queries/q_*); NEW files only, unapproved. Decisions in URGENT_TODO 'DECIDE (SKELETON_u'.

**Bottom line:** the shared skeleton is written, checked against STT_6.als, and the three family blocks already plug into it. Plugged into it, the current STT_6 defense block behaves exactly like STT_6.als: no counterexample under any perturbation the generator uses, and the same exhaustive count at exactly 3. Stage-1 cores now keep their symmetry break: 80 duplicate-free cores at `but 3` and `but 4`, against 129 from today's core, and 20 s instead of 46 s at `but 4`. It also turned up a real bug in the production SPT model: Alloy's 4-bit integer wraps at 8, so the operand caps let a transmitting branch carry 8 input registers. SAT in 6 s on SPT_6_oneLP_v2.als at its production scope; 0 of the first 3,000 SPT v2 instances have it, and the full corpus was not checked. No existing .als, parsexml, gem5, spec or paper file was edited, no git writes, and no Java of mine is running (lock released).

Files are all new, under `STAGE1_alloy/models/proposed/ultimate/`:
- `SKELETON_u.als` — the skeleton; every change vs STT_6.als tagged `-- [sk-n]`, defense slot between `//@@DEFENSE-BEGIN/END`.
- `blocks/STT_6.block.als` — the STT_6 block ported with the same meaning.
- `STT_6_skel_demo.als` — skeleton + that block (satisfiable at exactly 6: 20 instances in 2 s).
- `STT_6_skel_demo_core_ri.als` — the RI-only Stage-1 core of the demo.
- `derive_core_u.py` — assemble / check / lint / core / resize (`derive_core.py` untouched).
- `queries/` — `build_queries.py` rebuilds every `q_*.als`, `runq_u.sh` runs one under the lock, `runs.log` has one line per run.

### (1) Skeleton divergence inventory (vs STT_6.als outside its block, :320-332)
| Model | Divergence | Intentional or drift |
|---|---|---|
| STT_6_interleave, STT_all | none | — |
| Recon_6 | fold call passes `hardware_protection_policy[p]` (:239) | intentional |
| SPT_6_oneLP_v2 | `nonspeculative_xmit_p` in skeleton region (:251); fold, secure and tag_xm rewritten in Operand form (:253-315); dead `one_insecure` pred (:299) | intended meaning, drift in form |
| STT_6_v2, Recon_6_v2, SPT_6_oneLP_v3 | 4-line Operand retype (STT_6_v2:243-283) | intentional (A1 open) |
| STT_6_stl, STT_6_futuristic, STT_6_shadows | speculation-source helpers placed in the skeleton region (stl:283-288, fut:293-299, shadows:282-287); clause 2 rewritten in lockstep with clause 1 (stl:371) | intentional, drift risk |
| Recon_6_stl, SPT_6_oneLP_stl | state-based `stl_alias_atom` (:289/:292) instead of STT_6_stl's rf-based `stl_alias_pair` (:296) | drift |
| SPT_6_oneLP_stl | built from pre-v2 SPT: unperturbed seed (:386), `one_insecure` (:355) | drift |
| commitsplit, multisource | own commit-split facts and generator (:157-347); aggregate RR (:315-332) | intentional variants |
| s4, a3c, rmwjmp | extra runs placed first; rmwjmp renames `gen_lit`, which breaks the Stage-1.5 anchor | test drafts |
| all cores | derive_core.py's three edits; the symmetry break is stripped | intentional; the stripping is the problem |
| SPT_6, SPT_6_full, SPT_6_oneLP_noSTLF, STT_6_modified_protset | no rf fact; `first_uncommitted` lacks the empty-commit fallback (:139), so no instance with nothing committed is possible | legacy drift |
| STT_6_pincommit | STT_6 minus the rf fact (MANIFEST.md's claim is wrong) | legacy |

### (2) Feedback absorbed
- **rf_from_most_recent_writer:** a well-formedness fact in the one shared skeleton.
- **SPT seed bug class:** the seed signature must take `[p]`; the skeleton clips it to the surviving operands; `fed_p`/`unfed_p` express v2's seed exactly. A lint rejects reading the unperturbed program inside a block: it flags SPT_6_oneLP:341 and SPT_6_oneLP_stl:386, passes v2/v3 and the family blocks.
- **R-1 (instance-based protection):** the protection set is operand-typed for every family; a location rule is an exact lift (`ops_of`).
- **S-1 / Option B:** a new flow hook, `prot_flow_p`. SPT_6_u currently gets the same effect by passing only transmitter operands, which breaks if `Otherxs` ever transmits.
- **Contract variants:** untaint rules read the contract through `nonspeculative_p`, so STL / shadow / futuristic variants edit clause 1 only.
- **RI-only Stage 1 (Anna, binding):** `gen_core`; `core --minimality none` gives SPT's conservative core.
- **P3 / P5 off (binding):** P3 stays in the SPT block; P5 is the opt-in `rf_complete`, defined but not applied.
- **Stage-1.5 bound issues:** the Int wrap is removed by relational caps; fold depth, IX count and operand scope are regenerated by `resize`.
- **Post-hoc checker:** facts labelled well-formedness / vocabulary bounds / generation-only.
- **Core-relative minimality and ReCon B2(b):** minimality preds take a set argument, so these become a run-line change.

### (3) [sk-n] changes
| Tag | Change | Why | Effect |
|---|---|---|---|
| 1 | flag sigs are `one sig` | cleaner | none |
| 2 | spo-ordered index onto a prefix of IX0..IX5 | symmetry break stays valid at `but N` | same at exactly 6; cores 80 vs 129 |
| 3 | operand caps without `#` | 4-bit Int wraps at 8 | removes only wrap instances |
| 4 | two redundant facts folded | cleanup | none |
| 5 | `spo_p` = next surviving instruction | exact for any removal set | same |
| 6 | `rf_bridge_p` (old Mem→Mem half was dead) | clarity | same |
| 7 | operand-typed set + `ops_of` lift | one skeleton for all families | STT_6 exact |
| 8 | fold as a let-chain, renamed `protset_p` (old name kept as alias) | it never stopped at the commit point | same |
| 9 | single `flagged_p` | removes three hand-copied leak definitions | same |
| 10 | `prot_flow_p` hook | Option B without a skeleton edit | new interface function |
| 11 | `nonspeculative_p` declassification hook | variants stop re-deriving speculation | same on loads |
| 12 | `after_unresolved_p` library | helpers out of each file | same bodies |
| 13 | perturbed operand fields, `fed`/`unfed` | closes the seed bug class | — |
| 14 | dead helpers removed (`no_unresolved_mem_p` read the unperturbed program) | cleanup | none |
| 15 | named minimality preds with set arguments | core-relative minimality | `gen_useful_litmus` unchanged |
| 16 | facts grouped W / V / G | post-hoc checker | none |
| 17 | `rf_complete` (P5) | opt-in | off |
| 18 | run block between markers | a core differs in the run line only | partition and Stage-1.5 anchors intact |

### (4) Interface for the family agents
- **(1)** `speculation_contract_p[p]: Instruction`.
- **(2)** `hardware_protection_policy[p]: Operand` (seed); `prot_set_propagation_p[p,i,o]: Operand` (must return `o` when `i` is empty); `prot_flow_p[p]: Operand->Operand` (`op_edges_p[p]` for STT/ReCon, `none->none` when taint is computed inside clause 2).
- **(3)** `leakage_function: Operand`, on one line.
- **Optional:** tagged contract side-condition facts, which may use unperturbed relations.
- **Forbidden in funs/preds:** `Instruction.`, `Instruction -`, raw `rf`/`ddi`/`spo`, raw flag sets, `#`, redefining a skeleton name.

`derive_core_u.py assemble`, `check` and `lint` enforce this. The STT, ReCon and STL blocks in `blocks/` pass with 0 errors and 0 warnings.

### (5) Alloy evidence (`queries/runs.log`)
**Equivalence vs STT_6.als** (`for 9 but 6 Instruction`, new facts, tag_xm off):
- Structural check (spo_p, rf bridge, nonspeculative loads): 0 counterexamples (465 s).
- Leak predicate equal under no perturbation plus tag_xm (44 s), RR (95 s), RC+RR and RC alone (59 s), RS (79 s), RI (620 s): all 0.
- The direct generator-level check timed out at 900 s. It follows from the per-perturbation checks, because both generators are conjunctions of exactly those perturbation tests. RO was not run (unused).

**Facts:** old and new differ only through the Int wrap (counterexample: an ALU with 8 outputs); with no instruction holding 8+ operands they are equal (0, 161 s).

**Int wrap:**
- STT_6 at production scope: 0, both facts-only and under the generator.
- STT_6 at 12 operands: SAT under the generator (br_x with 8 inregs).
- Production SPT_6_oneLP_v2: SAT under the generator (6 s); 0 in the existing 3,000-instance v2 sample.
- The SPT_6_u port gap (256 vs 310) is entirely this: adding SKELETON_u's caps to SPT_6_u's own file gives 256.

**Exhaustive counts:**
- Flat at exactly 3: demo 80 = STT_6 80.
- Cores at `but 3`: 80 vs 129. At `but 4`: 80 vs 129, so STT has no 4-instruction cores; 20 s vs 46 s.
- P5 at exactly 3: 70 of 80.

**Relaxations:**
- RI not enforced in flat runs: SAT (three padding branches).
- RO not enforced in flat runs or in RI-only cores: SAT for both.
- Commit alone at the boundary does not secure: SAT.
- The commit boundary is always the unresolved gate branch: UNSAT (37 s).
- No unresolved non-branch appears in any generated instance: UNSAT (298 s).
- RI never removes a producer that has an older same-state writer, in any core: UNSAT (379 s). So rf_p not being recomputed is harmless there.
- The RS check timed out; RS holds by construction.

**Ports:** STT_6_u, Recon_6_u, STT_6_u_stl and SPT_6_u are all satisfiable on SKELETON_u. Exactly-3 counts match their own files: 80 = 80, 80 = 80, 396 = 396; SPT matches once the Int wrap is removed.

**Other:** `resize` to N=8 is satisfiable (flat 2 s, core 6 s). Throughput is 3,000 instances in 39 s vs 35 s for STT_6. partition_stage1.py works on the derived core (10 partitions).

### (6) Do the paper's relaxation claims match?
No.
- pipeline.tex:16 and :78 say a backbone is minimal over instructions, operands, states and flags. Operands are never enforced, and instructions only in Stage 1.
- pipeline.tex:110-121 describes RC as committing alone; the model tests commit and resolve together.
- pipeline.tex:134 ("RR, RC, RS only") is true only of the flat corpora.
- pipeline.tex:135 ("all instructions share necessary state") is contradicted by operand-less padding branches.

Proposed text for :16, for Anna to paste: "removing any of its instructions or state elements, resolving any of its unresolved instructions, or committing and resolving its first uncommitted instruction makes it non-violating."

### (7) Decisions for Anna (each with my labelled recommendation)
- **DECIDE 1: one operand-typed skeleton for every family.** Options: (a) adopt SKELETON_u everywhere; (b) keep per-family skeletons; (c) State-typed skeleton with an SPT exception. (a) changes no semantics by itself (STT_6 ports exactly). Recommendation: (a).
- **DECIDE 2: keep the symmetry break in cores.** Options: (a) keep the prefix index (80 vs 129, faster exhaustion); (b) strip it as today. Recommendation: (a).
- **DECIDE 3: the `prot_flow_p` hook.** Options: (a) add it inside clause 2; (b) keep the closure hard-wired and let SPT keep its workaround. Recommendation: (a).
- **DECIDE 4: what RI means.** Options: (a) collapse, as today (no ALU on a core's path); (b) delete (ALU chains become core content); (c) collapse plus recompute the most recent writer. Recommendation: (a); the query above shows (c) would change nothing in cores.
- **DECIDE 5: P5.** Your decision was off; it removes 10 of 80 at N=3. Recommendation: keep it off.
- **DECIDE 6: paper relaxation text** (URGENT_TODO:75). Options: rewrite the text, turn RO on, or present the figure as intent. Recommendation: rewrite as proposed.
- **DECIDE 7: padding branches** (pipeline.tex:135). Options: (a) fix the text; (b) ban operand-less branches. Recommendation: (a).
- **DECIDE 8: one STL alias fact.** The u-models and parsexml use the state-based form; the approved STT_6_stl is the rf-based outlier. Recommendation: state-based (STL owner's call).
- **DECIDE 9: SPT Int wrap.** Options: (a) apply the relational caps in the next regen via SKELETON_u; (b) patch SPT_6_oneLP_v2 now. Either way, scan the SPT v2 corpus and Stage-1 output for instructions with more than 2 inregs before using them. Recommendation: (a) plus the scan.

## ultimate (2026-11-09, audit-fanout-1109): SPT — SPT_6_u

Drafts in `STAGE1_alloy/models/proposed/ultimate/` (SPT_6_u.als, SPT_6_u_core.als, make_spt_u.py, queries/spt_*); NEW files only, unapproved. Decisions in URGENT_TODO 'DECIDE (SPT_6_u'.

**Bottom line.** I wrote a new ultimate SPT draft, `STAGE1_alloy/models/proposed/ultimate/SPT_6_u.als` (sha256 76f36f68…, 518 lines), and its Stage-1 core with SPT's own (conservative) minimality, `SPT_6_u_core.als` (bbd92485…). Both are built by `proposed/ultimate/make_spt_u.py`. The script hash-checks the approved `SPT_6_oneLP_v2.als` (acb1f2e2) and replaces only the defense block, so every skeleton line is byte-identical to v2. Clause 2 is now SPT's converged taint (paper §6.6 "Convergence"), so declassification, forward, backward and store-to-load untaint all actually happen. This fixes S-1 (all forms, including v3's store-fed residual), S-2/P3, S-3 and S-5 without editing the skeleton. Alloy and an independent Python port agree on every instance checked. No existing `.als`, parsexml, gem5, spec or paper file was touched, and there were no git writes and no .md files.

**Still open at hand-off.** The convergence query `conv_nop` started at 15:43:16Z under the lock, capped at 600 s. It ends on its own by about 15:53Z and its trap releases the lock. Its result will be in `queries/spt_runs.log`. Separately, the Python port measured a fixpoint depth of at most 2 steps over every perturbation view it evaluated (3,300 instances); the model uses 6.

#### 1. How SPT protects, untaints and declassifies

Sources: the paper is `~/Documents/quail/sources/papers/choudhary-2021-spt.pdf` (printed page = PDF page + 606). The gem5 tree is the local copy `~/trippel/defense_src/spt_0d2be0f/src/cpu/o3/`. E11 flags: `--scheme=SpectreSafeFence --applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy --freeParam=3`, shadow L1 off.

- **Security goal.** Definition 1 (p611 §6.2): data that is secret with respect to the non-speculative execution stays secret with respect to the speculative one. "Secret" means there is no dataflow from it to an operand of a transmit or control-flow instruction that leaks that operand.
- **Taint.**
  - All program data, memory and architectural registers, starts tainted (p612 §6.3).
  - Load outputs are always tainted at rename. Any other output is tainted iff some operand is tainted (p612 §6.3, p615 §7.3; gem5 `rob_impl.hh:236-249`).
  - Taint lives per physical register (`base_dyn_inst_impl.hh:450-475`, `setPartialTaint`). So untainting one reader untaints the producer and every other reader.
- **Protection.**
  - A transmitter with tainted operands is delayed until they untaint or it becomes non-speculative (p612 §6.3). In gem5, loads and stores use `fenceDelay = isAddrTainted()` (`lsq_unit_impl.hh:1140-1284`).
  - Branches use STT's rule (p612 §6.4). gem5 Lazy makes a tainted, not-unsquashable mispredicted branch's squash pending (`commit_impl.hh:943-962`). The squash is released only at the visibility point (VP), never on untaint (`rob_impl.hh:1059-1075`), which is stricter than the paper.
  - VP in the Spectre model: all older control-flow instructions have resolved (p609 §2.2.1; `rob_impl.hh:533-561`).
- **Declassification.**
  - Paper: the operands of transmitters and branches untaint when the instruction becomes non-speculative (p612 §6.3, p613 §6.6).
  - gem5: only load and store address registers, at the VP (`lsq_unit_impl.hh:1189-1209,1268-1280` → `cpu.cc:2133-2207`, `setAddrTaint(false)`). `untaintOtherTransmit` is a no-op with `moreTransmitInsts=0` (`cpu.cc:2212-2222`), so branch predicates are never declassified (audit B1).
  - On x86 a `jcc`'s operands are flags, and `test`/`cmp` have no backward rule. So even the paper's mechanism would not declassify the compared register.
- **Untaint rules.**
  - Load-immediate outputs are public (p612 §6.5).
  - Forward: all operands untainted → output untainted, never for loads (p613 §6.6; `rob_impl.hh:797-801`).
  - Backward: MOV, and invertible arithmetic with all but one input untainted (p613 §6.6, Fig. 4). gem5 applies it only to `add/addi/adc/adci/sub/subi/sbb/sbbi` with `numTaintedSrcRegs()==1` (which counts flags, audit A1) and to `mov` src 1 (which also hits cmov, audit A2) (`rob_impl.hh:853-880`).
  - Store-to-load (STL): rule ① store data public → load output public, and rule ② load output public → store data public, both gated by STLPublic (p613 §6.7, Fig. 5). In gem5 this is an AND-sync of load-destination and store-data taint while the load is uncommitted and the store is not completed, gated by `isSTLPublic` (`lsq_unit_impl.hh:1294-1409`, `lsq_unit.hh:630-659`).
  - Shadow-L1 memory taint (p614 §6.8) is off in our runs, so cache reads stay tainted.
  - gem5 re-applies the rules every cycle over the whole ROB, at most freeParam untaints per iteration (`rob_impl.hh:751-990`).
- **Flag variants.**

| flag | effect | how the model would change |
|---|---|---|
| `applyDDIFT=0` | plain speculative fence, no taint | protect everything speculative |
| `fwdUntaint=0` | no forward rule | drop `spt_fwd_p` |
| `bwdUntaint=0` | no backward rule | `InvOp` empty |
| `freeParam=0` | rule-based untaint inert; declassification and STL still act | keep declassification + STL only |
| `configImpFlow=Ignore` | no implicit-flow protection | drop `Branchxs.inreg` from leakage |
| `configImpFlow=Eager` | asserts out ("Eager scheme is disabled in SPT", `commit_impl.hh:920-922`) | not usable |
| `SpectreSafeInvisibleSpec` | unprotected loads in this tree (B2) | not SPT; don't model |
| `FuturisticSafeFence` | VP = all older instructions completed (`rob_impl.hh:556-557`) | contract = uncommitted and behind any unresolved instruction |

- **Scope of the guarantee.** The security proof assumes VP-reached instructions have non-speculative control flow and dataflow. That holds in the Spectre model only with control-flow speculation (p616 §8), so store-to-load speculation is outside SPT-Spectre's guarantee.

#### 2. Feedback absorbed and how the ultimate model handles it

- **S-1 (v2-4 plus the transitive check makes declassification dead).** Fixed by [u-1] and [u-2]: T1 is UNSAT in u and SAT in v2, and `g_t1` (with generation) is UNSAT.
- **v3 residual (producer load fed by a committed store).** Fixed: T1b is UNSAT in u and SAT in v3. This closes the model-fixes DECIDE "Option A incomplete" by doing Option B.
- **S-2 / P3 / SPT F5 (one-step lag, constant-derived transmitters).** Fixed by the fixpoint [u-5]: T2 is UNSAT in u and SAT in v2. This is 288 of 3,000 v2 instances.
- **S-3 / SPT F1 / SPT-3 (STL without STLPublic, and dead through the transitive term).** Fixed by [u-4]: the rule is now live (T4pass, T4bwd UNSAT in u, SAT in v2) and gated (T4gate SAT).
- **S-5 (backward untaint never fires).** v2 had no backward rule, and Stage 2 emits no gem5-backward-capable op on a path: bitnot is mov+not(xor), add is `leaq`, zsm is mov+imul, div is idiv. [u-3] adds the rule and an op class: T3inv is UNSAT, while T3noninv, T3two and T3spec are SAT. gem5 additionally needs the Stage-2 contract in §7.
- **SPT-1 / SPT-2 and paper-disagreement (4) (one forward pass in program order).** Handled by [u-1] and [u-3].
- **B1 (branch predicates).** Handled by [u-2], listed as DECIDE 2.
- **P1, P4 and the perturbation-aware seed (v2-1, v2-3, v2-2).** Kept unchanged. Every [u] function takes `p` and uses `o_p/i_p/rf_p/spo_p/uncommitted_p`.
- **P5 (unfed reads).** Measured but not fixed; it is a skeleton issue (§5).
- **Binding minimality decision.** SPT keeps its own minimality, so the core is conservative (RR/RC/RS, RO/RI commented), exactly as `SPT_6_oneLP_v2_core_conservative.als`.
- **SPT Stage-1 non-convergence (k4 ≈ 145k junk constant chains).** Under u, constant chains are public, so those cores cannot exist. The RI-only u core is 474 at `but 3` (exhausted; v2 546, v3 393); `but 4` did not finish in 600 s.
- **SPT STL (RS versus alias, generates 0).** Paper p616 §8 supports skipping it for E11 (DECIDE 7).
- **MODEL_AUDIT Q3 insertion rules 7-9.** Now checkable with u as the post-hoc oracle.
- **POSTHOC_GRAPH_CHECKER ("SPT needs an iterative fold").** u's clause 2 is exactly a step function, `spt_step_p`.

#### 3. Changes vs SPT_6_oneLP_v2 (marked `-- [u-n]` in the file)

| id | change (SPT_6_u.als line) | why | effect (evidence) |
|---|---|---|---|
| u-1 | `hardware_protection_policy[p] = leakage_function_p[p] - spt_public_p[p]` (:422); fold is the identity (:426); `spt_public_p` = 6 parallel steps of all rules (:494-503) | Paper §6.6 convergence. Transmitter operands have no outgoing rf/ddi edge, so the skeleton's `^op_edges` term becomes vacuous with no skeleton edit (audit "Option B" without touching `secure_*`/`tag_xm`) | Lost vs v2: 288 constant-derived and 3 S-1 out of 3,000, nothing else. T1/T1b/T2/T3c: u UNSAT vs v2/v3 SAT |
| u-2 | Declassify only addresses of non-speculative loads/stores (:438-447); ALT line for branch predicates at :445-446 | gem5 B1 plus x86 flags semantics | Gained vs v2: 100/100 sampled are B1. T5n: u SAT, v2 UNSAT |
| u-3 | Backward rule on `InvOp` (:461); `sig InvOp in Instruction`, `InvOp in Otherns`, needs an input and an output, plus a canonical reach-a-load/store-address-or-store-data fact (:513-517) | Paper rules 1-2; S-5. The model cannot know the concrete op, so the class is a Stage-2 contract | T3inv u UNSAT; T3noninv, T3two, T3spec u SAT |
| u-4 | STL both ways (:486), STLPublic (:468), store-uncommitted gate (:477, ALT :476); a data-less store counts as public (Stage 2 emits it as `movq $0`, `parsexml.py:2712-2716,2730-2733`) | Paper §6.7; gem5 sync conditions | T4pass, T4bwd u UNSAT vs v2 SAT; T4gate, T4comm u SAT |
| u-5 | Forward rule over all register inputs (:454) | Paper §6.6; `rob_impl.hh:797-801` | T2 UNSAT; the 288 lost instances |
| u-6 | Initial registers public (:440) | Same as v2-2's seed, now stated directly (p612 §6.5) | unchanged |

#### 4. Alloy evidence

All runs are at `exactly 6`. Log: `queries/spt_runs.log`; witnesses: `queries/spt_out/`.

- **Satisfiable.** `SPT_6_u.als` gives 200 instances in 229 s. The Python port finds all 200 u-useful.
- **Lost differential (Python, 3,000-instance v2 sample).** 2,709 useful in both, 288 lost as constant-derived (P3), 3 lost as S-1, 0 other. The port agrees with Alloy that all 3,000 are v2-useful.
- **Gained differential (Alloy, InvOp empty, capped at 100, 278 s).** All 100 are B1; Python agrees on all 100.
- **Facts-only shape queries.** Each u query takes about 85 s; v2/v3 queries take about 1-7 s.

| query | u | v2 / v3 | means |
|---|---|---|---|
| T1 (S-1) | UNSAT | v2 SAT | declassification works |
| T1b (store-fed residual) | UNSAT | v3 SAT | v3 residual closed |
| T2 (constant chain) | UNSAT | v2 SAT | forward fixpoint, no lag |
| T3inv (backward) | UNSAT | v2 SAT | backward rule fires |
| T3c (forward after declassification, Fig. 4c) | UNSAT | v2 SAT | rules compose |
| T3noninv | SAT | — | no backward through a non-invertible op |
| T3two | SAT | — | two tainted inputs: rule must not fire |
| T3spec | SAT | — | speculative reader declassifies nothing |
| T4pass (STL forward) | UNSAT | v2 SAT | STL rule live |
| T4bwd (STL backward) | UNSAT | v2 SAT | rule ② works |
| T4gate | SAT | — | STLPublic gate holds |
| T4comm | SAT | — | committed-store timing gate holds |
| T5n | SAT | v2 UNSAT | branch predicates no longer declassified |

- **Generation-level.** `g_t1` is UNSAT (213 s): S-1 tests are never generated. `g_t3two` is UNSAT (239 s) and `gnoRS_t3two` is SAT (216 s): state-minimality (RS) alone prunes near-miss untaint context (DECIDE 5).
- **Not done.** `conv_facts` (convergence under all perturbations) was stopped by the cap; `conv_nop` is running (see top). The A2-probe pair was not run; it has the same structure as t3two.
- **Caveat.** My first shape round was vacuous: a bare `c in j.outreg.rf` is true for an empty `c`. It was fixed with a guard `rd[c,j]` and rerun; the model itself was unaffected.
- **Op-class duplication.** 182 of the first 200 instances contain an InvOp, mostly on xm's own address path, where the class cannot change a verdict (DECIDE 3).

#### 5. Skeleton issues (for the skeleton owner)

1. The transitive `^op_edges` term in `secure_speculation_scheme_p`/`tag_xm` is a forward-taint closure. It overrides any defense's untaint. u neutralizes it by handing over only edge-free transmitter operands. Either document that contract, or drop the term and let each defense return its final taint.
2. P5, unfed reads: in 985 of 3,000 v2 instances (32.8%), a register input reads a state that an earlier instruction wrote, with no rf edge; 37 of these are on xm's own operand. The program reads the earlier writer's value, but the model assumes an initial constant. Proposed fact: an input whose state has an earlier writer must be rf-fed by the most recent one.
3. The fold has 7 hard-coded positions, so it truncates on programs longer than 7 instructions (the post-hoc checker trap). This does not affect u.
4. Dead or inconsistent code: `no_unresolved_mem_p` uses the unperturbed `uncommitted`/`spo`, and `first_uncommitted_p` lacks the no-committed fallback. Both are unused in SPT.
5. The RR clause forbids unresolved non-branch instructions other than the first uncommitted one, and implies the DESIGN.md "xm branch always resolved" invariant, which is a consequence of the clause, not just an empirical observation (0 of 3,000 counterexamples).
6. Cosmetic: a stray "å" in the IX0 comment.

#### 6. DECIDE items (Anna's call; the recommended option is what is implemented, unless stated otherwise)

1. **How to fix S-1/S-2/S-3.**
   - (a) u as built: Option B entirely inside the defense block, no skeleton edit.
   - (b) Drop `^op_edges` from the skeleton for every family.
   - (c) Keep v3 and bucket the residuals with a diagnostic.
   - **Recommendation: (a).**
2. **B1, branch predicates.**
   - (a) Not declassified: u's default, matching gem5 and the paper's x86 flags reading.
   - (b) Declassified: the ALT line at :445-446, the paper's ISA-abstract reading and v2's behavior.
   - (c) Ship both as variants.
   - **Recommendation: (a).** It is the source of all 100 gained instances, and none of them is a false positive on gem5-spt.
3. **InvOp canonicalization.**
   - (a) As built: the class is allowed wherever its output can reach any load/store address or store data. This never loses a test, but the first instances are full of on-path InvOp variants.
   - (b) Tighter: exclude xm's own operands from the relevance target. Fewer duplicates; loses a rare two-transmitter edge case under RR.
   - (c) No InvOp at all, so the backward rule stays dead as in v2.
   - **Recommendation: (a) now**, and switch to (b) if the enumeration cap starts to bite.
4. **Timing gates.**
   - STL only from an uncommitted store, i.e. one still in the SQ (default), or from any store (ALT :476).
   - Forward/backward rules on committed instructions: convergent (default), or uncommitted instructions only (more tests, with false positives whenever gem5 wins the retire race).
   - **Recommendation: keep both defaults.**
5. **Near-miss untaint context is pruned by RS** (`g_t3two` UNSAT vs `gnoRS_t3two` SAT). The flat corpus never contains the tests that check SPT does not over-untaint (the A1/A2 class).
   - (a) Stage 1.5 or fanout inserts that context, with u as the post-hoc oracle.
   - (b) An RS exemption for untaint-context states, which is a generation change.
   - (c) Accept the gap.
   - **Recommendation: (a).**
6. **SPT Stage 1.**
   - (a) Keep the conservative core (decided).
   - (b) Revisit RI-only: u's RI core is a small 474 at k3; k4 is still unknown.
   - **Recommendation: (a)**, and measure k4 on cafe2 before revisiting.
7. **SPT STL.** **Recommendation: skip for E11.** This is option (c) of the existing DECIDE, now backed by paper p616 §8.

#### 7. Stage-2 and harness follow-ups

1. **Op-class contract.**
   - An InvOp with 1 input is emitted as `movq in0,out`; with 2 inputs as `movq in0,out; addq|subq in1,out`. The destination must be a register with a public prior value, because gem5's `mov` reads its destination as a merge source (`regop.isa:751-753`). An InvOp's blank slots must never be filled.
   - Any other ALU must be an op with no SPT backward rule: `imulq`, `idivq`, `andq`, `orq`, or `cmov_rr` (the A2 probe).
   - Never use `inc`/`dec`/`adc`/`sbb`/`neg` for a non-InvOp ALU.
   - Today's emissions are all gem5-non-invertible: bitnot, `leaq` add, zsm and div (bitnot and `leaq` add are invertible only in the paper's sense). So **u can run on E11 before any parsexml change**.
2. **parsexml.** Read `this/InvOp` from `sig_atoms` (the parser already loads every sig) and carry an `inv` flag per record. Only needed to exercise backward untaint in gem5.
3. **stage_seed.py.** Pin InvOp membership per core instruction; today it pins only kinds, operands, rf/ddi, spo and xm.
4. **STL realizability.** Stores with an Alloy address write to `probe_mem[rN]` (`parsexml.py:2701-2716`), so their store-to-load rf edges are not same-address forwards and gem5 is stricter there. Only constant-slot stores really forward.
5. **Post-hoc checker.** Evaluate `spt_step_p` iteratively, one eval per step.

#### Files

All new, all in `/Users/annaeaton/trippel/simspect/STAGE1_alloy/models/proposed/ultimate/`:

- `SPT_6_u.als` (the ultimate draft)
- `SPT_6_u_core.als` (conservative Stage-1 core)
- `make_spt_u.py` (generator)
- `queries/build_spt_queries.py`, `queries/run_spt_queries.sh`, `queries/spt_semantics.py`
- `queries/spt_A_shapes.als`, `queries/spt_A2_shapes.als`, `queries/spt_B_gen.als`, `queries/spt_C_lost.als`, `queries/spt_C_gained.als`, `queries/spt_C_sample_u.als`, `queries/spt_D_ucons_b3.als`, `queries/spt_D_ucons_b4.als`, `queries/spt_D_ucons_b5.als`, `queries/spt_D_uri_b3.als`, `queries/spt_D_uri_b4.als`, `queries/spt_D_uri_b5.als`, `queries/spt_E_conv.als`
- `queries/spt_runs.log` and `queries/spt_out/` (results and witnesses)

Note: an entry in `spt_runs.log` from another session ("ultimate-recon-spt", 12:23Z) says it stopped its own queued SPT runs and that none ran.
