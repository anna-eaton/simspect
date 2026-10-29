# Audit: `STAGE1_alloy/models/SPT_6_oneLP.als` vs the SPT paper (2026-10-28)

**Scope:** read-only audit of the canonical SPT model (362 lines) against Choudhary et al., "Speculative Privacy Tracking (SPT)", MICRO '21 (`~/Documents/quail/sources/papers/choudhary-2021-spt.pdf`, pages = PDF page numbers via `pdftotext -f/-l`). **Nothing was edited. No `.als` was touched.** Every fix below is a proposal for Anna; each one is a Stage-1 change and needs an `xml --force` regen and a re-sweep (batch it with `wiki/state/ALLOY_MODEL_CHANGES.md` §A). I found these by reading the code. I did not run the Alloy evaluator, so the "verify" notes say what to check on a copy.

**Already known, so cross-referenced here and not re-reported:** (1) the protection-set over-approximation, `hardware_protection_policy` l.341 → `ALLOY_MODEL_CHANGES.md` §A1. (2) `rf` is not tied to the most recent writer (clobber) → §A2 and `ALLOY_RF_LASTWRITER_BUG.md`. (3) `freeParam=0` made gem5 fwd/bwd untaint inert, a harness problem and not a model problem → claudenotes 2026-06-10 "sptDiscrepancy". (4) `Otherx` is excluded from the leakage function, which matches gem5 `moreTransmitInsts=0` → same claudenotes entry.

## What matches the paper (no action)

- **Visibility point = Spectre model.** l.337 `speculation_contract_p = uncommitted & has_unresolved_brs` (has_unresolved_brs = after an unresolved branch, l.238-240). Paper p3: "in the Spectre model (which covers control-flow speculation), it is when all older control-flow instructions have resolved". Because `committed_last` (l.137) makes the committed instructions a prefix, the non-speculative instructions form an spo prefix that ends at the first unresolved branch.
- **Transmitters = load address, store address, branch predicate.** l.344 `Loads.inaddr + Branchxs.inreg + Stores.inaddr`. Paper p9: "For loads/stores, delaying execution (including TLB accesses, etc.) until the address operands are untainted". Paper p5: data leaks if it "gets passed as an operand to a transmit or control-flow instruction".
- **Threat model / what is protected.** Paper p5 Definition 1: "If data D is secret with respect to the non-speculative execution, then D is secret with respect to the speculative execution". Paper p6: "all program data (memory and architectural registers) starts off as tainted". The seed at l.341 is all operands except `Inreg`/`Inaddr` with no rf producer. That exception is consistent only because Stage 2 initialises unproduced registers with immediates, which §6.5 (p6) untaints ("SPT untaints the output register of 'load immediate' instructions").
- **Declassification at the VP.** l.220 `nonspeculative_xmit_p` with l.349. Paper p6: "the operands of transmitters/branches are untainted when the instruction becomes non-speculative".
- **Forward ALU rule.** l.353 untaints an `other` output when no inreg is in the set. Paper p7: "if all of the instruction's operands are untainted, then its output register becomes untainted". Load outputs are only untainted through memory rules, which matches p6: "Output registers of loads are always (conservatively) tainted at rename".

## Findings, ranked

### F1 (HIGH, false-positive source): the final check's forward closure undoes the untaint rules, so the STL rule at l.357 is effectively dead

l.259 / l.271 / l.279-280 count a speculative xmit operand as leaking if it is in `P` **or in `P.^(op_edges_p)`**, where `P = last_committed_protset_p`. `P` is already seeded with almost every operand (l.341), so the closure term adds back only the operands that the untaint rules *removed* while a still-protected ancestor exists.

The concrete case is the STL rule at l.357. It removes `L.outreg` and `L.inmem` when the forwarding store's data is untainted. No rule ever removes a store's `Outmem`, though: l.349 removes it only inside a declassified backward cone, and l.351/353/356/357 never touch `Outmem`. So `S.outmem ∈ P` survives, and `S.outmem -rf-> L.inmem -ddi-> L.outreg -rf-> xmit` re-protects the transmitter.

Paper p8, §6.7 STL rule ①: "If S's data operand gets untainted, then L's output register should be untainted (forward Load untaint)". Paper p8, §6.8 L1D rule ①: "When untainted store data is written to the L1D, the L1D taint of the written address range is cleared".

**Effect:** the model emits "leaks" where SPT legitimately untaints. Now that `--freeParam=3` turns gem5 untaint on, these should show up as SPT hits that are artifacts. They may be among the untriaged store / store-forward hits in claudenotes 2026-06-10. Whether this fires also depends on F4 (optional `ddi`).

**Proposed fix:** either (a) drop the `^op_edges` term in l.259/271/280, because the propagation pass already carries taint forward (a consumer keeps taint unless l.356 removes it); or (b) add the missing rule "store `Outmem` is untainted when all its data inregs are untainted", with the STLPublic gate from F3. Verify on a copy that `gen_lit` stays SAT and that STL-from-untainted-store instances disappear.

### F2 (HIGH, coverage gap for the research target): backward untaint removes the whole transitive backward cone, which is much more aggressive than SPT

l.349 removes `(i.operands & nonspeculative_xmit_p).*(~op_edges_p)`: every ancestor of a declassified operand, through any ALU, through loads (`~ddi` Outreg→Inmem), and through store forwarding (`~rf` Inmem→Outmem, then `~ddi` to the store's data).

Paper p7: "We use backward untaint rules for several instruction types: ① For register MOV instructions (r2 = r1): if the output is untainted, then the operand is untainted. ② For invertible arithmetic instructions (e.g., ADD): if the output is untainted and all but one of the inputs are untainted, then the remaining input is untainted". Across memory, the paper only untaints the store data "If L's output register gets untainted" (§6.7 rule ②, p8), and only under STLPublic (F3).

**Effect:** the model treats as public some data that SPT keeps tainted, such as both inputs of `r0 = r1 + r2` when only `r0` is declassified. So it never generates tests that would catch a gem5-spt **over-eager backward untaint** bug, which is exactly the untaint-algebra bug class SPT adds. This is a coverage gap, not a false-positive source.

**Proposed fix:** replace l.349's cone with the declassified operand itself plus per-instruction backward rules applied in the propagation pass. For a 1-inreg `other`: output untainted → inreg untainted. For a 2-inreg `other`: output untainted and the other inreg untainted → the remaining inreg untainted. A producer's outreg is untainted when its consumer inreg is declassified (same physical register, the `~rf` step). For memory, use F3's STLPublic-gated rule.

### F3 (MED-HIGH, coverage gap): the STL untaint at l.357 is the "naive" rule the paper says leaks, because it ignores STLPublic

l.357 untaints `L.outreg + L.inmem` whenever the rf-source store has untainted data. It never checks that the store/load **address** operands are untainted.

Paper p8: "whether there is a memory dataflow edge may itself be a secret, if one of the store/load address operands is tainted. Untaint propagation must not leak the existence of such secret edges (i.e., address aliases)". The paper gives the condition: "STLPublic(S, L) holds, the attacker knows based on non-secret information that L obtains its data via forwarding from store S (and no other store)". Figure 5 caption: "Naive untaint propagation over store-to-load forwarding leaks tainted data".

**Effect** (if F1 is fixed so that l.357 actually takes effect): the model would never flag a gem5-spt implementation that does naive STL untaint, which is the Figure 5 bug class.

**Proposed fix:** gate l.357 on `S.inaddr ∉ o` and `L.inaddr ∉ o`, and on there being no other older store with a tainted address between S and L. This interacts with §A2 (rf last-writer).

The rule also requires `inreg.Inreg`, so a store whose data has no inreg (an immediate) is never treated as untainted data. Check how Stage 2 concretises such a store. If gem5 sees immediate data, it untaints it (§6.5) and this becomes a small false-positive source.

### F4 (MED): `ddi` edges are optional, so the dependence graph can omit real data dependences

l.155 and l.161-164 only **upper-bound** `ddi` (`no ddi - (~ins).outs`, plus per-kind allowed shapes). Nothing requires `ld.inmem→outreg`, `str.inreg→outmem`, or `other.inreg→outreg` to exist. The concrete program always has these dependences.

The backward cone (l.349) and the final closure (l.259/271/280) both follow `ddi`. So the same concrete program can be judged leaking or not leaking depending on which edges Alloy chose, and the enumeration contains both variants. Combined with F1, an STL-from-untainted-store instance counts as a "leak" only when the load's `ddi` is present.

**Proposed fix:** `fact ddi_complete { all i: Instruction | i.inmem->i.outreg + i.inreg->(i.outreg+i.outmem) in ddi }`, restricted to the kinds allowed by l.161-163. Verify on a copy that this stays SAT and check how much the instance count changes.

### F5 (MED, false-positive source): one forward pass in spo order, with no fixpoint, so older instructions are never re-evaluated after a later declassification

l.225-236 apply `prot_set_propagation_p` once per position (f, f.spo, … f.spo⁶). Paper p7: "untainting of a register by instruction I can cause instructions both younger and older than I to untaint registers in the next cycle(s)". Paper p7 also says it "examines each in-flight instruction at most 3 times".

**Example:** `I0: ld r2←[m]`, `I1: r5 = r2 ⊕ k`, `I2: ld [r2]` (non-speculative, declassifies r2), then speculative `ld [r5]`. Once r2 is declassified, SPT forward-untaints r5. The model already processed I1 while r2 was tainted and never revisits it, so `r5` stays protected and the test is emitted as a violation that gem5 correctly lets through.

**Proposed fix:** run the 6-deep `a[]` sweep 2-3 times. Taint only decreases, so 3 sweeps over 6 instructions are enough. The commented-out l.222 nests the rule three times at the *same* instruction, which does not fix ordering.

### F6 (MED, false-positive source): a conditional `Branchn` predicate is never declassified

l.120 allows an `inreg` on `Branchns`. Stage 2 lowers that to `br_cond` on the register (`parsexml` INSTRUCTION_TABLE). l.344 counts only `Branchxs.inreg`, so a **non-speculative** conditional `Branchn` never declassifies its predicate.

Paper p5: data leaks if it "gets passed as an operand to a transmit or control-flow instruction". Paper p6: "the operands of transmitters/branches are untainted when the instruction becomes non-speculative". gem5-spt untaints it, but the model keeps it (and its backward cone) protected, which can produce a false-positive "leak" downstream.

**Proposed fix:** add `Branchns.inreg` to the declassification side only, as a separate `declassify_function` used by `nonspeculative_xmit_p`. Alternatively, forbid `inreg` on `Branchn`.

### F7 (LOW): `TOtherx` is semantically identical to `TOthern` in this model

l.35 / l.75 define `TOtherx`, but `Otherxs` contribute no leakage operands (l.344, by design, see claudenotes). Every rule treats `Otherns + Otherxs` the same way (l.119, 163, 351, 353). As a result, an instance with an `Otherx` filler duplicates an `Othern` one and wastes the `max_instances` budget (compare §B1/B3). **Proposed fix:** add `fact { no Otherxs }` to this model, or document the duplication.

### F8 (LOW): dead code, latent bugs, and stale comments

- `no_unresolved_mem_p` (l.251-253) uses the unperturbed `uncommitted` / `spo` instead of the `_p` versions. It is a latent bug if the Futuristic-model contract (commented-out l.336) is ever re-enabled. Note that the Futuristic VP (p3: "when the access instruction cannot be squashed") is not modelled at all.
- `no_unresolved_mem` (l.144), `no_unresolved_brs` (l.141) and `no_unresolved_brs_bf_or_is_p` (l.247) are unused.
- l.351 is subsumed by l.353: an `other` with no inreg has no inreg in `o`.
- Stale or wrong comments: l.333 says "Specific defense model STT"; l.341 says "all the input memory" (it is all operands); l.41-43 say IX3-5 are "spo position 2"; l.5 is an STT-era header; l.38 has a stray `å`.

### F9 (LOW, cross-reference correction): the premise of §A1 misstates SPT's protection scope

`ALLOY_MODEL_CHANGES.md` §A1 says "The real STT/SPT defense only protects values derived … from a speculative load / memory read" and proposes sources = `Loads.outreg` + read memory. That is STT's scope. SPT's scope is broader (p4: "We protect both speculatively-accessed data and non-speculative secrets … our protection scope is broader than STT's"; p6: "all program data … starts off as tainted").

The §A1 fix is still acceptable for SPT **only because** Stage 2 initialises unproduced registers with immediates (§6.5). The doc should say so, so that nobody later ports it to a model or harness where registers start with real values.

## Suggested order for Anna

Batch F1 and F4 with §A1/§A2 in one regen, since all four are false-positive sources that touch the same closure and propagation code. Then do F5 and F6, which are cheap. F2 and F3 add coverage and change what "secure" means, so decide them as a design question: does SimSpect's SPT oracle follow the **paper's** untaint algebra exactly? If it does, F2 and F3 are required, and they are how gem5-spt untaint-algebra bugs become detectable.
