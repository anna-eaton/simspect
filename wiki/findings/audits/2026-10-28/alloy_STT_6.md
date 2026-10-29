# Audit: `STAGE1_alloy/models/STT_6.als` vs. the STT paper (2026-10-28)

**Scope:** read-only audit of the canonical STT model (`STT_6.als`, 333 lines, unmodified in the working tree; last touched by commit `e298a9e`) against Yu et al., *Speculative Taint Tracking*, MICRO 2019 (`~/Documents/quail/sources/papers/yu-2019-stt.pdf`; page numbers below are **PDF pages**, extracted with `pdftotext -f N -l N`). Nothing was edited. Every proposed fix is a `.als` change and needs Anna's per-change sign-off (root `CLAUDE.md`, Alloy models STRICT). Known issues already in `wiki/design/DESIGN.md` and `wiki/state/ALLOY_MODEL_CHANGES.md` are cross-referenced, not re-reported as new.

## What the model gets right (checked against the paper)

- **Visibility point = Spectre model.** Paper p.5 §6.1: "In the Spectre model, an instruction has reached the visibility point if all older control-flow instructions have resolved." Model: `no_unresolved_brs_bf_or_is_p` (:254-256) counts both `Branchxs+Branchns` as control flow, and `speculation_contract_p` (:325) is `uncommitted & has_unresolved_brs_p`. Match. (The `uncommitted &` is redundant, since anything after an unresolved branch is uncommitted by :134/:137, but harmless.)
- **Taint source = loads.** Paper p.5: "We focus on the case where access instructions are loads ... STT taints the output of any speculative access instruction." Model: `hardware_protection_policy = Mem_s` (:326); memory reaches registers only through `ld_ddi` `Inmem->Outreg` (:171), so register taint can only originate at a load. Match, with the caveat in F4.
- **Untaint at visibility point.** Paper p.5: "STT untaints the output of an access instruction once it becomes safe." Model: `prot_set_propagation_p` (:331) drops the memory read by any load with no older unresolved branch. Since "Instructions reach the visibility point in fetch order" (p.5), every safe load precedes every unsafe one, so the order-free final protset (`last_committed_protset_p`, :232-243) is equivalent. Match, with the caveat in F4.
- **Propagation.** Paper p.6 §6.2: "an instruction's output register is tainted if any of its input registers are tainted." Model: forward reachability `^(op_edges_p)` over `rf+ddi` (:264), so one tainted input is enough (union semantics). Match. Taint also flows through memory (store `Inreg->Outmem` :172, then `rf`), which STT does not track ("STT does not require tracking taint in any part of the memory system ... or across store-to-load forwarding", p.6). This is harmless because the load that receives the value is unsafe anyway.
- **Explicit transmitters.** Paper p.5: "Classifying only loads as transmitters will block memory system-related explicit covert channels ... We assume that stores trigger a cache coherence invalidation only on retirement, or else are defined as transmitters." Model: `leakage_function = Loads.inaddr + Branchxs.inreg` (:328). Loads match; leaving stores out matches the paper's retire-time-store assumption.

## Findings, ranked

### F1 (High, doc correctness): `ALLOY_MODEL_CHANGES.md` §A1/§A2 do not match `STT_6.als` as it stands

- **A2 is already in STT_6.** `fact rf_from_most_recent_writer` is present at `STT_6.als:161-169`, word for word the "Option A" text in §A2. `git log -S rf_from_most_recent_writer` shows commit `e298a9e` added it. §A2 says "Nothing here is applied ... Validated on a copy (no real `.als` touched)". That is stale for STT_6. **Action:** fix the doc. More important, **check the provenance of the STT_6 testset actually swept.** If its XML was enumerated before `e298a9e`, the clobber shapes are still in the results even though the model is fixed. `testsets/STT_6/` is not on this Mac, so this could not be checked here; check on cafe2 (compare XML mtimes against the commit time).
- **A1's root cause does not apply to STT_6.** §A1 describes a policy that seeds "essentially all operands", which is `SPT_6_oneLP.als:341` (`Instruction.operands - ((Inreg + Inaddr) - Instruction.outreg.rf)`). STT_6 uses `hardware_protection_policy: State {Mem_s}` (:326). A const-address ALU output has no path from a `Mem_s` operand, so STT_6 cannot produce the const-addr false positive. The rerun matrix row "STT | ✅ (shared policy)" looks wrong for STT_6. **Action:** fix the matrix so nobody makes an unneeded STT edit. Do re-check the other `STT_*` variants one by one, since some may share SPT's policy.

### F2 (High, coverage gap vs. paper): implicit branches, especially store-to-load forwarding, are not modeled

- **Paper:** p.5 §6.1: "To block implicit channels, STT requires the microarchitect to classify explicit branch instructions ... and to identify the implicit branches that represent additional sources of data-dependent resource usage, e.g., store-to-load forwarding, memory consistency speculation". p.8 §6.4.2: "store-to-load forwarding creates an implicit channel because the load M2 accesses the cache only if it does not alias with the store S ... the store-to-load forwarding implicit branch predicate checks that every older in-flight store does not alias with the load ... impIf (AND{S | in-flight store S older than M2} S.addr ≠ &Y[r0])". Memory-dependence speculation is "simply a prediction of the store-to-load forwarding implicit branch" (p.8). The paper's Table 1 (p.5) lists "Store-load forwarding | Imp | Imp".
- **Model:** `leakage_function` (:328) covers a tainted *load* address. It has no transmitter for a tainted *older store's* address feeding a younger load's alias check. A test where the secret reaches only a store address, and an untainted-address younger load reveals it through whether it forwards or hits the cache, can never be generated. This is the paper's Fig. 9 shape.
- **Cross-ref (partly known):** `ALLOY_MODEL_CHANGES.md` §B5 lists "store-address transmitter (→KV3)" as backlog, and an untracked `STAGE1_alloy/models/STT_6_stl.als` exists (not audited here). New in this audit: the paper's exact STT semantics for that transmitter. In STT the store address acts as an implicit-branch *predicate* of the younger load, not as a cache-access transmitter. SPT_6_oneLP's `+Stores.inaddr` (`SPT_6_oneLP.als:344`, commented "stores transmit their address (cache access)") is therefore the wrong rationale to copy for STT.
- **Proposed (not applied):** `fun leakage_function : Operand {Loads.inaddr + Branchxs.inreg + (Stores & (^spo).Loads).inaddr}`, which makes a store's address a transmitter only when some younger load exists whose forwarding decision depends on it. This needs a matching gem5 observable: the younger load's forward-vs-cache fate. `check_ld._xmit_cache_fate` already separates `store_forward` from `reached_cache`, so a checker variant keyed on the younger load is plausible. Owner-gated. Validate SAT on a copy first.

### F3 (Medium, coverage gap, new framing of a known invariant): an xmit branch is always "resolved", so the resolution-based channel is never exercised by a mispredicted secret-dependent branch

- **Paper:** p.7 §6.4: "Resolution-based channels are eliminated by delaying the effects of branch resolution until the branch's predicate becomes untainted." The motivating example (Fig. 5/6, p.4, "Resolution-based implicit channel") is a squash caused by a secret-dependent misprediction.
- **Model:** the per-instruction resolution-minimality clause `all i: (unresolved - first_uncommitted) | secure_speculation_scheme_p[RR->i]` (:306) forces every transmitting `Branchx` to be resolved. Resolving the xmit branch changes neither its own membership in `speculation_contract_p` (that depends on *older* branches) nor its predicate's taint, so the clause would be unsatisfiable otherwise. `DESIGN.md` records this invariant (30k instances, 0 unresolved) only as a fact that keeps a codegen bug dormant. Per `DESIGN.md`, Stage 2 then emits the xmit branch as `correctly_not_taken`.
- **Why it matters:** if the concretized xmit branch is always correctly predicted, its resolution never squashes. Then the STT mechanism under test (delaying the squash until the predicate is untainted) has no visible effect, and br_x tests may only catch secret values that happen to flip the direction. **To verify (not done, out of time):** how `check_br.py` classifies a correctly-predicted xmit branch.
- **Proposed (owner decision):** exempt `xm & Branchxs` from the RR clause, i.e. `all i: (unresolved - first_uncommitted - (xm & Branchxs)) | ...`, and let Stage 2 mispredict it. This turns on the dormant duplicate-PC NOP path, so apply the `DESIGN.md` "What to do if you change the model" step 2 fix in `parsexml.py` first. Related to §B2 (relax per-branch minimality), but B2 targets multi-branch/OTB shapes, not this one.

### F4 (Medium, under-approximation): untaint is keyed on memory *location*, not on the load instance

- **Paper:** p.6 §6.2: "If a load is unsafe, its output is always tainted." p.5: "STT taints the output of any speculative access instruction."
- **Model:** `prot_set_propagation_p` (:331) removes `(safe load).inmem.opstate`, a *State*, from the protection set. Every operand with that State then counts as untainted (`last_committed_protset_p[..].(~opstate)` at :264/:272), including the `Inmem` of a later *unsafe* load reading the same location. The model therefore calls an unsafe load's output untainted whenever any safe load read the same `Mem_s`. STT taints it.
- **Compounding:** `ld_ddi` (:171) has only `Inmem->Outreg`, so a tainted address does not taint the load's output. Paper p.6: "output register is tainted if (1) it is an access instruction or (2) any of its input (physical) registers are tainted". An unsafe load whose location was declassified therefore breaks a load→load→xmit chain even when its address is tainted.
- **Effect:** coverage only, not false positives. These shapes are judged secure, and RS-minimality (:310) excludes any instance where such a state is off the leak path. Shapes lost: "safe read of X, then speculative re-read of X feeding a transmitter", and aliasing safe/unsafe load pairs.
- **Proposed:** seed taint from unsafe-load *outputs* (operand-typed, the way SPT already uses an `Operand` policy), e.g. `fun taint_src_p[p] : Operand {(Loads & has_unresolved_brs_p[p]).outreg}`, and test `no (taint_src_p[p] + taint_src_p[p].^(op_edges_p[p])) & speculative_xmit_p[p]`. Optionally add `Inaddr->Outreg` to `ld_ddi`. RS-minimality then needs re-validation, since an `Inmem` state is no longer the source. Separately, the :330-331 comment says loads "remove their inaddr" but the code removes `inmem`; fix the comment.

### F5 (Low-Medium, enumeration waste and labeling): `TOtherx` is semantically identical to `TOthern`, and `TBranchn` with a predicate contradicts STT

- `Otherxs` appears only in the kind tag (:35, :76) and in facts shared with `Otherns` (:119, :173). The `Otherxs.inreg` transmitter is commented out (:327 vs :328), and `tag_xm`/`one_xm` (:269-273) can never pick an Otherx as `xm`. So any instance with k "other" instructions can be enumerated up to 2^k times as Othern/Otherx relabelings. That spends the `max_instances` budget (compounds §B1), and Stage 2 still labels them `other_x` (`parsexml.py:106`) although they never transmit. **Proposed:** `fact no_otherx {no Otherxs}` for STT_6. Alternatively, restore `Otherxs.inreg` if variable-latency ALU transmitters are wanted (paper p.5: "Classifying all instructions that have operand-dependent hardware resource usage as transmitters will block all explicit channels").
- `TBranchn` is "a branch that doesn't transmit", but STT protects *all* explicit branches (p.5, "classify explicit branch instructions"). A Branchn with a tainted speculative predicate is judged non-leaking. Low impact, since a Branchx of the same shape covers it. **Proposed:** `fact {no Branchns.inreg}`, so Branchn means "predicate-less/unconditional", which is how it is already used as the window opener (see F8).

### F6 (Low, vacuous constraint): the first conjunct of `secure_speculation_scheme_p` and the first disjunct of `tag_xm` can never fire

`last_committed_protset_p ⊆ Mem_s` (:326, and :331 only removes), while every `leakage_function` operand is `Inaddr`/`Inreg`, which facts `ia_s`/`ir_s` (:110-111) force to `Reg_s`. So `no (protset.(~opstate) & speculative_xmit_p)` (:263) is always true and `some (protset.(~opstate) & speculative_xmit_p & xm.operands)` (:271) is always false. The semantics are unaffected, but this is dead logic: anyone reading it would believe "a protected state used directly as a transmitter operand" is checked. **Proposed:** delete both halves, or keep them deliberately with a comment saying they are vacuous under a `Mem_s` policy.

### F7 (Low, latent bug): `no_unresolved_mem_p` mixes perturbed and unperturbed relations

`no_unresolved_mem_p` (:258-260) uses `uncommitted` and `spo` instead of `uncommitted_p[p]`/`spo_p[p]` (compare `no_unresolved_brs_p`, :249-252). It is used only by the commented-out contract at :324, so it is dormant. If that contract is re-enabled, RC/RI perturbations would silently be ignored for memory. The :324 contract is also not the paper's Futuristic model ("an instruction has only reached this point if it cannot be squashed", p.5): it is a *union* `no_unresolved_brs + no_unresolved_mem`, which includes almost everything uncommitted. Flag it before anyone reuses it.

### F8 (Info, mostly known, cross-ref §B2/§B3 and `ENUMERATION_OVERSPECIFICATION.md`): consequences of the minimality clauses

- **RR at :306.** Resolving a non-branch has no effect, so every unresolved non-branch other than `first_uncommitted` makes the run UNSAT. All uncommitted non-branches are therefore marked resolved.
- **Joint RC+RR at :308.** This is only satisfiable when `first_uncommitted` is itself the unresolved speculation-source branch.
- **At most one window-opening branch.** A second unresolved branch is never individually necessary, which is §B2.
- **RS at :310.** `all s: State | secure[RS->s]` requires *every* State to lie on every leak path. A window-opening branch with its own predicate register, or an xmit load with its own `inmem`/`outreg` state, makes the run UNSAT. Instances therefore get predicate-less window branches (they rely on the `--branch-ann-file` BTB force), and xmit loads either lack `inmem`/`outreg` or reuse leak-path states. A reused `Mem_s` on an xmit load whose address is the secret is also a concretization oddity worth a `parsexml` look.
- **Unused RI machinery.** `fix_rf_hole_p`, `spo_p` under RI, and `f[p]` (:213-225) are never exercised, because `gen_useful_litmus` never uses RI (§B3).

### F9 (Cosmetic)

- IX3-IX5 comments all say "spo position 2" (:41-43), and there is a stray `å` at :38.
- `committed_resolved` (:134) duplicates `committed_in_resolved` (:211).
- `last_committed_protset_p` is the protset after *all* instructions, not at the last committed one. Its 7th step `f.spo^6` (:233) is a no-op at `exactly 6 Instruction`.
- `first_uncommitted_p` (:209) lacks the empty-committed fallback that `first_uncommitted` (:139) has. It is unused.

## Not checked (time limit)

- `check_br.py` behaviour on correctly-predicted xmit branches (F3).
- STT_6 testset XML timestamps against `e298a9e` (F1).
- Running the proposed fixes in the Alloy analyzer for SAT/UNSAT.
- `STT_6_stl.als`.

Each proposed fix must be validated on a *copy* of the model before Anna signs off.
