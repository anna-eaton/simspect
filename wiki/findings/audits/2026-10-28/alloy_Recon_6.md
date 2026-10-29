# Audit: `Recon_6.als` (and a glance at `STT_6_multisource.als`) vs the ReCon paper

2026-10-28, audit subagent, read-only. No `.als` was edited and nothing was run in Alloy. Everything below comes from reading `STAGE1_alloy/models/Recon_6.als` (325 lines), `STT_6.als`, `STT_6_multisource.als` and the paper `~/Documents/quail/sources/papers/aimoniotis-2023-recon.pdf`. That PDF is a 3-page extraction and pdftotext reports xref errors, so page cites are to the extracted pages p1/p2. The claims about what the model can and cannot generate were worked out by hand from the relational definitions. Before acting on F1 and F2, confirm each with a forcing-predicate SAT check (exact predicates are given below).

**Already known, not re-reported (cross-references):** the protection set over-approximation (`ALLOY_MODEL_CHANGES.md` A1). The rf / last-writer clobber (A2; the rerun matrix lists `Recon_6` as needing it, and see F3 for its status). The OTB shape is absent from STT_6 because of the cap and ordering (`OTB_GENERATION_GAP.md`). The `getOldestTaint` mechanism (`wiki/results/reconresults.md` Bug 1).

## Ranked findings

### F1 (critical): Recon_6's only ReCon-specific clause is a semantic no-op, so Recon_6 is effectively STT_6 without the A2 fix

Recon_6 differs from STT_6 in exactly two ways (`diff STT_6.als Recon_6.als`). First, the parameterised `hardware_protection_policy[p]` (Recon_6.als:316-318) is `Mem_s - (~opstate).(^(op_edges_p[p]).(~inaddr).(Loads-speculation_contract_p[p]))`. It removes from the initial protection set every Mem_s that flows backwards, through one or more rf/ddi hops, into the address of a non-speculative load. Second, Recon_6 lacks `rf_from_most_recent_writer` (see F3).

The removal adds nothing. The fold `last_committed_protset_p` (222-233) applies `prot_set_propagation_p` (321-324) to all 6 instructions, and line 323 already removes `inmem.opstate` of every load that has no older unresolved branch (`no_unresolved_brs_bf_or_is_p`, 244-246). Every Mem_s in the HPP removal set is one of two things. It may be the `inmem` of a load (only loads have `inmem`: lines 117-120). Or it may be the `outmem` of a store, which reaches the closure only through an rf edge into some load's `inmem`, and that edge carries the same state (`same_state_rf`, 159). In both cases the load is spo-older than the non-speculative consumer load, because every rf hop goes forward in spo (`unidirectional_rf`, 158). `has_unresolved_brs_p` (235-237) is upward-closed in spo, so that older load is also non-speculative. Its state is therefore already removed by line 323.

`Loads - speculation_contract_p[p]` (with `speculation_contract_p` at 315) is the same set as the loads that the fold treats as non-speculative. A `committed_p` load can never sit behind an unresolved branch (`committed_last` 137 plus `committed_resolved` 134). So the final protection set under every perturbation `gen_lit` uses (RR, RC, RS) is identical to STT_6's.

Consequence: no Recon_6 instance exercises ReCon's reveal/conceal behaviour. The Recon-vs-STT difference on gem5-recon is untested by the model.

Paper basis for what should be modelled: the address is revealed only when the dependent load commits. "When the second load (LD2) of a load-pair commits, the address accessed by the first load (LD1) is marked as revealed" (§5.2, p2). Only a speculative load of a revealed word gets an untainted result: "for STT [56], any load that receives a revealed value untaints its destination register" (§5.4, p2).

### F2 (critical, STT-shared, does not look like A1): the STT fold already treats any non-speculatively loaded word as public, which is more permissive than both STT and ReCon

Line 323 is state-based, not instance-based. When a speculative load reads the same Mem_s atom as an older non-speculative load, its result is treated as unprotected: `last_committed_protset_p` no longer contains that state, so `secure_speculation_scheme_p` (252-255) never flags the chain.

The paper says STT does not do this. "In both NDA and STT ... potential secrets are speculatively accessed values that might be squashed" (§3.1, p1). STT "taints the output register of a speculative load instruction" (§2.2, p1). ReCon relaxes this only for values "made public through non-speculative execution" (§3.1), meaning leaked by a load pair, not merely loaded.

So the model never generates three kinds of test:

- **(a)** A test where a speculative re-load of a non-speculatively loaded word feeds a transmitter. Plain STT must block this.
- **(b)** A test where ReCon must still block that re-load because the word was loaded but never dereferenced by a committed load pair.
- **(c)** The positive ReCon case, which F1 makes vacuous anyway.

This is the opposite direction from A1, which is about too much protection, so it is not covered there. A quick grep of `ALLOY_MODEL_CHANGES.md` found no entry for it. It needs Anna's decision because it touches every STT_* model.

Proposed fix (not applied). Make the fold instance-based by removing the non-speculative load's *output*, not its memory state. That means taking the transitive closure from protected sources instead of from states, which is the same direction as the A1 "source-derived taint closure" redesign. Fold it into A1.

### F3 (high, known as A2, status check): Recon_6 still lacks `rf_from_most_recent_writer`

STT_6.als:160-169 and STT_6_multisource.als:163 have the Option A fact. Recon_6 has nothing between lines 159 and 161. Any Recon_6 testset is still exposed to the clobber false positives (`ALLOY_MODEL_CHANGES.md` A2 says about 58.6% of `SPT_6_oneLP` is clobber-shaped). Add the fact verbatim when the A-batch lands. The rerun matrix row for `Recon_6` ("policy shared? verify") can now be answered with F1.

### F4 (high, applies if F1 is fixed): even as intended, the reveal is transitive, but the paper limits it to direct load-to-load pairs

`^(op_edges_p[p])` (317) follows ALU ddi (163) and store-to-load memory hops. The paper says "RECON limits its detection to only the leakage of load pairs with a direct dependence" (§4.3, p1), and "RECON would not detect a load pair since there is no direct dependence between two load operations" (§5.1.1, p2). An immediate offset is still a pair (§4.3), and that is invisible to the model anyway.

Over-revealing means the model treats more data as public than ReCon does. Load → ALU → load reveal cases would never be generated as violations, so a gem5-recon build that wrongly untaints there would be missed. This is coverage loss, not false hits.

Proposed (not applied) single-hop reveal:

`fun revealed_p[p] : State { (Loads.inmem).opstate & (~opstate).((~inmem).(Loads & (rf_p[p].((Loads - speculation_contract_p[p]).inaddr)).~outreg)) }`

The intent is: the `inmem` state of a load LD1 whose `outreg` rf-feeds the `inaddr` of a non-speculative LD2. For the paper-faithful variant, use `committed_p` for LD2 (detection at commit, §5.1). Then make only *speculative* loads of a revealed state produce an untainted output (instance-based, see F2), and require the pair to be spo-older than the reusing load.

### F5 (medium): conceal (store commit clears the reveal bit) is not modelled

"upon the commit of a store instruction, the bit of the corresponding word is cleared" (§5.2, p2). There is also §4.4.1 (performed stores) and §4.4.2 (in-flight stores in the store buffer). Any reveal removal at 316-318 is global and order-free: no store kills it, and a younger pair could "reveal" for an older load. Today the spec contract makes the ordering point moot, but the conceal point is not. A ReCon model has to order three things: reveal (LD2 commit) before the reusing load, with no committed store to the same Mem_s in between. Otherwise the most security-relevant ReCon tests (a stale reveal after a store) are never generated.

### F6 (medium): the speculation contract is branch-only, but ReCon's evaluation also uses store speculation

The paper says "For evaluation, we use only speculation cast by control flow and store instructions" (§3.1, p1), and memory-dependence speculation creates implicit channels (§4.5.2). `speculation_contract_p` (315) uses only `has_unresolved_brs_p`. The memory variant is commented out (314), and `no_unresolved_mem_p` (248-250) is dead code that also uses the unperturbed `uncommitted` and `spo`. Check which speculation sources the gem5-recon `--scheme` runs actually use (not verified here) before deciding whether this matters.

### F7 (high, about the planned OTB model): STT_6_multisource's relaxation is cancelled out by boundary clause (c), so it still cannot generate the two-branch getOldestTaint gadget

The gadget (reconresults.md Bug 1) needs two unresolved branches: branch_outer before load_A, then branch_inner before load_B, then the merge, then the transmitter. Clause (c), `secure[RC->first_uncommitted + RR->first_uncommitted]` (STT_6_multisource.als:323; Recon_6.als:298), requires that committing and resolving the first uncommitted instruction *alone* secures the program.

Committing has no effect here. `first_uncommitted` is never in `has_unresolved_brs` because everything older is committed and hence resolved. RR only matters if that instruction is an unresolved branch. So (c) is equivalent to "first_uncommitted is an unresolved branch whose resolution alone secures the program." For the gadget, resolving branch_outer leaves load_B speculative under branch_inner, so (c) is false and the instance is excluded.

(c) also implies the relaxed (b), `secure[RR->unresolved]` (line 320), because security is monotone in resolution. So in multisource (b) is redundant. The only effect of the relaxation is to admit extra, unnecessary unresolved instructions after the first-uncommitted branch. Single-branch two-load merges were already admissible in STT_6 (OTB_GENERATION_GAP.md).

Confirm with a SAT check on a scratch copy (with Anna's OK): force two unresolved branches B1 → ld_A → B2 → ld_B → other(ld_A.out, ld_B.out) → xm.inaddr. I expect UNSAT.

Proposed fix (not applied): replace (c) with an aggregate boundary clause, such as `secure[RC->first_uncommitted + RR->unresolved]` or simply require `first_uncommitted in unresolved & (Branchns+Branchxs)`. Keep per-branch *contribution* minimality (the alternative already commented in multisource around lines 327-332) so redundant branches stay out.

### F8 (low): transmitters and multi-source loads

`leakage_function` (320) is `Loads.inaddr + Branchxs.inreg`, with Otherx commented out (319). That matches the paper's statement that ReCon adds no transmitters ("RECON does not affect either of them", §3.1). But `TOtherx` instructions can still exist and can never be the transmitter. `limited_inaddrs` (123) gives loads a single address source. That is consistent with the paper's evaluated configuration ("we focus on evaluating the case where there exists only a single direct load dependence and leave multi-source operations for future work", §5.1.1). So per-operand pairs for x86 base+index loads are outside the model's scope. Note this in the model's README rather than changing it.

### F9 (low, hygiene; no semantic effect)

- The comments for IX3, IX4 and IX5 all say "spo position 2" (41-43), and line 38 has a stray `å`.
- `committed_in_resolved` (201) duplicates `committed_resolved` (134).
- `first_uncommitted_p` (199) has no `else` branch for the case where nothing is committed, unlike `first_uncommitted` (139). It is currently unused.
- `last_committed_protset_p` (222-233) hard-codes 7 fold positions. With more than 7 instructions, later loads would silently drop out of the fold. That is fine at `exactly 6 Instruction` (307) but fragile.
- The comment on line 323 says "remove their inaddr", but the code removes `inmem`.
- `gen_useful_litmus` (296) applies `secure[RR->i]` to non-branch unresolved instructions too. That forces every non-branch instruction except `first_uncommitted` to be resolved, which is probably intended, but it is undocumented.

## What to decide (Anna)

1. Treat Recon_6 as "STT_6 minus A2" until it is rewritten (F1, F3). Do not read Recon_6-vs-STT_6 gem5 differences as model signal.
2. A paper-faithful ReCon model needs three things together: a direct-pair reveal at LD2 commit (F4), a conceal on store commit (F5), and an instance-based untaint (F2, folded into A1).
3. Fix clause (c) in STT_6_multisource before generating the OTB testset (F7), and confirm with the UNSAT check first.
