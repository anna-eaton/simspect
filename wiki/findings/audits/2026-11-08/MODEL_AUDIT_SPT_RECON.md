# Model audit: SPT_6_oneLP_v2 and Recon_6 (leakage semantics), 2026-11-08

Session model-audit, read-only. No `.als`, `parsexml.py`, gem5, hook or spec file was edited. Every Alloy claim below comes from a query run on a scratch copy (recipe and predicates in "Queries run"); every gem5 claim cites the source tree; every paper claim cites page and section. Builds on: `wiki/findings/audits/2026-10-28/alloy_SPT_6_oneLP.md` (SPT F1-F9), `alloy_Recon_6.md` (Recon F1-F9), `APPROVALS.md`, today's `SOURCE_AUDIT_{SPT,RECON,SUMMARY}.md`, `wiki/state/ALLOY_MODEL_CHANGES.md` (P1-P5) and `wiki/state/EVAL_MANIFEST.md` (v2 table). Where an older audit made a claim "by reading", this audit says whether a query confirmed it.

**Direction legend.** **U (unsound):** the model calls a case safe that the defense must block, so no test is generated for it and a gem5 bug there is missed. **I (incomplete):** the shape is outside the model's vocabulary or speculation sources, so it is never generated either, but because the model cannot express it, not because it judges it safe. **O (over-strict):** the model calls a case a leak that the defense legitimately allows, so it produces false-positive hits (noise to triage, not missed bugs). **C:** correct.

## Verdict: SPT_6_oneLP_v2.als (row E11) and its core `proposed_twophase/SPT_6_oneLP_v2_core_ri.als`

Compared against the paper (Choudhary et al., MICRO'21, `choudhary-2021-spt.pdf`; printed page = PDF page + 606) and gem5-spt @ 0d2be0f with E11's flags (`--scheme=SpectreSafeFence --applyDDIFT=1 --fwdUntaint=1 --bwdUntaint=1 --configImpFlow=Lazy`, classic caches, shadow L1 off, `moreTransmitInsts=0`).

| Clause (v2 line) | vs paper | vs gem5 (E11) | One-line reason |
|---|---|---|---|
| Speculation contract `:369` (uncommitted and behind an unresolved branch) | C (Spectre model); I for store/memory-dependence speculation | C; I for STL | gem5 VP = every older control op executed (`rob_impl.hh:518-561`); no STL in the model |
| Leakage function `:378` (ld addr, st addr, br_x predicate) | C | C | `moreTransmitInsts=0`: only loads/stores untaint/delay (`cpu.cc:2133-2222`, `lsq_unit_impl.hh:1140-1284`) |
| Protection seed `:375` | C | C | load outputs always tainted (p612 §6.3; `rob_impl.hh:236-249`); unfed registers are load-immediates in the program (p612 §6.5) |
| Declassification `:384` [v2-4] together with the transitive check `:286-303` | **O, new regression** | **O** | Q1: declassifying a load-derived value is dead in v2 (SAT), was live in pre-v2 (UNSAT) |
| Forward untaint `:386-391` | O | O | one-step lag (P3 / SPT F5) and the transitive check both keep untainted outputs protected |
| Backward untaint (only via v2-4's rf rule) | C (conservative) | C | gem5 backward rules fire only on `add/sub/adc/sbb/mov` microops (`rob_impl.hh:853-880`); our vocabulary emits `lea`, `xor`, `imul`, `idiv` |
| STL untaint `:392` | U in principle (no STLPublic gate), dead in practice | same | cancelled by the transitive check whenever the load has its ddi edge (SPT F1); the missing gate only matters for alias channels the model cannot express (I) |
| Branch-predicate declassification (br_x in leakage) | C | gem5 stricter (B1), harmless | gem5 never untaints branch predicates |
| v2-1 `rf_from_most_recent_writer` | C | C | 0/3000 stale rf in the v2 sample (pre-v2: 63%) |
| v2-2 perturbation-aware seed | C | C | equal to the old seed at `no_p` (manifest `eq_base` 0; not re-run here) |
| v2-3 at least one insecure transmitter | C | C | strictly adds instances |
| Minimality `gen_useful_litmus` `:343-355` (+ RI in the core) | I (per-branch minimality, ALLOY_MODEL_CHANGES B2) | I | RI core: an ALU on the transmitter path survives only through the P3 lag (see Q2) |

**Overall SPT:** no unsound clause that affects generated tests. The model protects a superset of what SPT protects, and v2-4 made the superset much larger than intended: every value that came out of a memory-reading load stays protected forever, so SPT's headline feature (declassification) is never exercised as "allowed", and tests where gem5-spt legitimately lets the transmitter go will be scored as hits.

## Verdict: Recon_6.als (row E6) and its core `proposed_twophase/Recon_6_core_ri.als`

Compared against the paper (Aimoniotis et al. 2023, `aimoniotis-2023-recon.pdf`; the PDF extracts as 3 text chunks without printed page numbers, so cites are by section) and the authors' docker tree `~/Downloads/dockerrecon/gem5-recon` (E6 runs `gem5-recon-modded --scheme=2 --allow_leaked`, classic `--caches`).

| Clause (Recon_6 line) | vs paper | vs gem5 (E6, classic caches) | One-line reason |
|---|---|---|---|
| Speculation contract `:315` (branch shadows only) | I | I | paper §3.1 and `decode.cc:686-690`: conditional branches AND stores cast shadows; STL draft `proposed/Recon_6_stl.als` covers it |
| Leakage function `:320` (ld addr, br_x predicate) | C | C | build delays tainted loads and tainted branches; store-address leaks don't count (Anna, 2026-11-08) |
| Reveal clause `:316-318` | no-op (query QR2 UNSAT) and wrong even as intended | inert | transitive through ALUs, LD2 merely non-speculative (not committed), no conceal (paper §4.3, §4.4, §5.1); gem5 reveal is dead on classic caches (R-SA-1) |
| Propagation `:323` (STT fold: a non-speculative load makes its *location* public) | **U** | **U** | QR1a/QR1c: a speculative re-load of a non-speculatively loaded word is never a leak in the model; STT taints it and ReCon reveals only after a committed load pair |
| Skeleton: `rf_from_most_recent_writer` missing | O + broken meaning | O | 775/3000 instances read a register past a newer writer (125 feed the transmitter); after Stage 2, 50/3000 programs' transmitter reads an ALU result of constants instead of the modelled load |
| Minimality / perturbation | I (same as STT_6) | I | RI core: an ALU on the transmitter's register path is always removable (UNSAT up to 5; STT_6 core exhausted at 6) |

**Overall Recon:** Recon_6 is STT_6 without the rf fact. Its one unsound clause is the shared STT fold (Recon F2 / STT-3 of the 10-28 audit, now confirmed by query); it also sits in STT_6. Its missing rf fact makes about a quarter of instances unrealisable as programs.

## Evidence: SPT

### S-1 (new, O, high): v2-4 plus the transitive check makes declassification of load-derived values dead

- **Mechanism.** `secure_speculation_scheme_p` (`:286-303`) flags a speculative transmitter operand if it is in the protection set `P` **or in `P.^(op_edges_p)`**. The seed (`:375`) protects every `Inmem`, `Outmem` and `Outreg`, and nothing ever removes a load's `Inmem` or a store's `Outmem` except the STL rule. v2-4 (`:384`) declassifies only the transmitted operand and its rf producer (`.*(~rf_p)`), so the producer load's `Inmem` stays in `P`, and `Inmem -ddi-> Outreg -rf-> (speculative reader)` re-flags every other reader of the declassified value. Pre-v2 used `.*(~op_edges_p)`, which also removed the load's `Inmem` (and was unsound in the other direction, SPT F2), so declassification worked there.
- **Query Q1** (predicate below): "a non-speculative load transmits value V; the speculative transmitter `xm` reads the same V (same rf producer); `xm`'s operand is not in `P`" together with `gen_useful_litmus` at `exactly 6`. **v2: SAT in 7 s. Pre-v2 `SPT_6_oneLP.als`: UNSAT, exhausted in 20 s.**
- **Witness (v2, program order):** `ld r0 <- [M0]` (committed) ; `br` (committed) ; `ld [r0]` (committed, transmits r0) ; `br` UNRESOLVED ; `ld [r0]` = xm (speculative) ; `br`. The model scores the last load as a leak.
- **What SPT does with it.** Paper p612 §6.3: "the operands of transmitters/branches are untainted when the instruction becomes non-speculative"; p611 Definition 1: r0 is no longer secret once the non-speculative execution transmits it. gem5: the committed load reaches the VP with a tainted address, `untaintMemTransmit` clears its address taint (`lsq_unit_impl.hh:1189-1209`, `cpu.cc:2133-2207`); the speculative load reads the same physical register (v2-1 guarantees no newer writer), so it is not delayed. So every such test is a guaranteed false-positive hit.
- **Frequency.** In the 3,000-instance v2 sample (`results/spt_v2_20261108/xml_v2`), 3 instances have exactly this "same value transmitted non-speculatively" shape; the effect is wider, because the same cancellation applies to forward untaint (an ALU whose inputs were declassified, SPT F5) and to STL untaint (SPT F1). Stage 1.5 (flat model, RI off) can add a non-speculative reader to any core, so the shape will appear in the eval corpus too.
- **The v2 brief's expectation was wrong in one respect.** `EVAL_MANIFEST.md` (v2-4 row) and `ALLOY_MODEL_CHANGES.md` P2 say "the existing input rule then clears the value's other readers". It does clear them from `P` (`:391`), but the transitive term re-adds them. This is not unsound; it only adds false positives, which is the direction Anna asked for ("generate too many rather than too few"), but it is larger than intended and it hides exactly the feature that distinguishes SPT from STT.
- **Proposed diff (defense clause 2 plus the check; for Anna, not applied).** Option A, smallest: also declassify the producer load's memory read, but only for the transmitted value, i.e. `- (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p]))` becomes
  ```
  - (let d = (i.operands & nonspeculative_xmit_p[p]).*(~(rf_p[p])) | d + (d & Loads.outreg).(~(ddi_p[p])))
  ```
  This stops at the load's `Inmem` (one ddi hop back from the declassified `Outreg`), so it does not reintroduce the SPT F2 over-untaint through ALUs or across stores. Option B (SPT F1(a)): drop the `^op_edges` term from `secure_speculation_scheme_p` and `tag_xm`, and make the propagation compute forward taint explicitly (fix P3 so outputs use the updated input set). B is the principled fix but changes much more; validate either with the same differential the v2 brief used ("old-useful and not new-useful" restricted to realisable instances) plus Q1 returning UNSAT.

### S-2 (known, O): forward untaint lags one step and is overridden by the transitive check

Confirmed by the SPT core witness under Q2 (below): `ld r0` (committed, no `Inmem`) ; `br_x r0` UNRESOLVED (its predicate is a non-speculative transmitter, so `:384` declassifies r0) ; `r0' = op(r0)` ; `ld [r0']` = xm. At the `op` step, `:391` removes the op's input from `P` but `:388` reads the old set, so `r0'` stays protected (P3). Per the paper (forward untaint, p613 §6.6) r0' is public and the xm may issue. gem5 happens to agree with the model here only because it never declassifies branch predicates (SOURCE_AUDIT_SPT B1). Known as P3 / SPT F5; not applied on purpose (manifest E11 note: constant-derived transmitters ~10% of v2 instances).

### S-3 (known, U in principle, I in practice): STL untaint has no STLPublic gate

`:392` untaints a load's output when the store it reads from has public data. The paper (p613 §6.7) requires STLPublic: the load's address untainted and every store between S and L (including S) with an untainted address. Without the gate the model would call a transmitter of L's value safe while an intervening store's address is tainted, which is exactly the alias channel of the paper's Fig. 5. In practice the rule is dead whenever the load has its `Inmem->Outreg` ddi edge, because the store's `Outmem` is never removed from `P` and the transitive term re-flags (SPT F1), and the case it would get wrong needs memory-dependence speculation, which the model doesn't express. Not run as a query (reasoned from the clauses above). Proposed diff if F1 is ever fixed: gate `:392` on `(S.inaddr + L.inaddr) not in o` and no spo-between store with an `inaddr` in `o` (SPT F3 text).

### S-4 (C): seed, contract, leakage

- Seed: loads always taint their destination in gem5 ("Access instructions always taint their destination (regardless of speculative or not)", `rob_impl.hh:236-241`) and in the paper (p612 §6.3); the model protects every load's `Inmem`/`Outreg`. Registers with no in-program writer are public in the model; the paper starts all architectural registers tainted (p612 §6.3), but Stage 2 initialises those registers with `movq $0` (`parsexml.py` pass 5 `ssa_init`), which the paper untaints (p612 §6.5, load immediate) and gem5 untaints (no tainted source, `rob_impl.hh:246-249`). So the seed matches the program that actually runs. (SPT F9 makes the same point.)
- Contract: gem5's Spectre VP is `isPrevBrsResolved` = every older control instruction `readyToCommit` without fault (`rob_impl.hh:533-561`); the model's `has_unresolved_brs_p` is the same notion. Loads behind a store with an unknown address are not speculative in either (STL is handled by STLPublic, §6.7, not by the VP).
- Leakage: with `moreTransmitInsts=0`, gem5 delays and untaints only loads and stores (`lsq_unit_impl.hh:1140-1284`) and delays branch squashes with tainted predicates (`commit_impl.hh:944`); the model's `Loads.inaddr + Branchxs.inreg + Stores.inaddr` matches. `Otherxs` are not transmitters in either. Stores still have no checker (E11 note).

### S-5: why gem5 backward untaint never fires in today's corpus

gem5-spt backward-untaints only when the microop name is a substring of `"add,addi,adc,adci,sub,subi,sbb,sbbi"` or equals `"mov"` (`rob_impl.hh:853-880`). Stage 2 emits `add` as `leaq` (microop `lea`, `arch/x86/isa/microops/ldstop.isa:687-703`), `bitnot` as `movq; notq` (`not` = `limm; xor`, `insts/general_purpose/logical.py:327-331`), `zsm` as `movq; imulq` (`mul1s/mulel/muleh`, `multiply_and_divide.py:152-156`), `div` as `movq; cqo; idivq` (`parsexml.py:2365-2460`). The only `mov` microops are intermediate copies whose outputs are never transmitted non-speculatively. So with today's vocabulary, the only SPT untaint events that can reach a path value are direct declassification of the same physical register and forward untaint. This matters for Q3: adding register `add`/`sub`/`mov` forms to the vocabulary (VOCAB_TABLES) turns on backward untaint.

## Evidence: Recon

### R-1 (confirmed, U, shared with STT_6): the STT fold makes a location public on any non-speculative load

- **Clause.** `:323` removes `inmem.opstate` of every load with no unresolved older branch. The protection set is a set of locations, so a later speculative load of the same location counts as reading public data.
- **Query QR1a** (facts only, no minimality, `exactly 6`): "xm's address comes straight from a speculative load l3 of location A; an older non-speculative load l1 read A; l1's value is never any load's address (no load pair); nothing forwards into l3". **Recon_6: UNSAT (2 s). STT_6: UNSAT (2 s).** Control **QR1c**, identical except l1 reads a different location: **SAT for both.** So the only thing that makes the model refuse the test is the shared location. (With `gen_useful_litmus` both are UNSAT, because RS-minimality rejects the control's unneeded location; that is why the facts-only form is the right test.)
- **What the defense does.** ReCon paper §3.1: in STT and NDA "potential secrets are speculatively accessed values that might be squashed"; ReCon relaxes this only for values already "made public", and §4.1/§4.3/§5.1 define that as a direct load pair whose second load commits; §5.4: only "any load that receives a revealed value untaints its destination register". gem5 (E6): loads under a shadow are tainted (`decode.cc:691-693`), and the reveal that could untaint them never reaches the right block on classic caches (R-SA-1), so l3's output is tainted and the transmitter is delayed.
- **Direction and nuance.** U against both the paper and the build: a gem5 failure to delay this transmitter would never be tested. The one argument for the model's choice is value-level: l3 returns the same value l1 put in a register before speculation, and STT does not protect register values that exist before speculation (ReCon §3.1, "Register Protection"). If Anna adopts that value-level reading, this becomes a deliberate scope choice rather than a bug, but then it must hold only when no store wrote A in between, which the model doesn't check (no rf edge is required into l3; P5).
- **Proposed fix (needs Anna; same as 10-28 STT-3 / Recon F2).** Make protection instance-based: protect the outputs of speculative loads, not locations. Sketch for Recon (operand-typed protection set, like SPT v2):
  ```
  // LD1 -> LD2 direct pair (no ALU between), LD2 committed: LD1's word is revealed (ReCon §4.3, §5.1)
  fun revealed_p[p: PTag->univ]: State {
    { s: Mem_s | some ld1, ld2: Loads & i_p[p] | ld2 in committed_p[p] and s in ld1.inmem.opstate
                 and some (ld1.outreg.(rf_p[p]) & ld2.inaddr) } }
  // speculative loads' memory reads are the sources; revealed words are not
  fun hardware_protection_policy[p: PTag->univ]: Operand {
    ((Loads & speculation_contract_p[p]).inmem & o_p[p]) - revealed_p[p].~opstate }
  fun prot_set_propagation_p[p: PTag->univ, i: Instruction, o: Operand]: Operand { o }
  // last_committed_protset_p / secure_speculation_scheme_p / tag_xm: Operand form, as in SPT_6_oneLP_v2.als:256-315
  // still missing: conceal (a store to the word between LD1 and the re-load cancels the reveal, §4.4)
  ```
  For STT_6 the same without `revealed_p`. The `revealed_p` line is a sketch, to be written properly (direct rf from LD1.outreg to LD2.inaddr, LD2 committed, no store to the state between LD1 and the reuse) and validated on a scratch copy; conceal-on-store is part of it. Whether to do it now is a decision (below), because on classic caches the gem5 side is plain STT anyway.

### R-2 (confirmed): the reveal clause is a no-op

- **Query QR2** (facts only): "some memory state removed by `hardware_protection_policy[p]` that is not the location of a load the fold treats as non-speculative", for `p` = `no_p`, every `RR->i`, `RC+RR->first_uncommitted`, every `RS->s`. **UNSAT, exhausted in 823 s** at `exactly 6`. So Recon_6's final protection set equals STT_6's under every perturbation `gen_lit` uses (10-28 Recon F1 / R-1, previously by reading only). The 10-28 audit's proof by reading (Recon F1) is: every revealed state is the `Inmem` of a load spo-older than a non-speculative load, hence itself non-speculative, hence already removed by `:323`; and `Loads - speculation_contract_p[p]` equals the fold's non-speculative loads for loads, because committed instructions precede every unresolved branch (`committed_last`, `committed_resolved`). I re-derived that argument and agree.
- Even as intended, the clause is wrong: it reveals transitively through ALUs and stores (`^op_edges`), at LD2 non-speculation rather than commit, and never conceals (paper §4.3: "RECON limits its detection to only the leakage of load pairs with a direct dependence"; §5.1: detection at commit; §4.4: stores conceal). It errs permissive (would be U), but is inert today.

### R-3 (confirmed, O and broken meaning): `rf_from_most_recent_writer` is missing

- Measured on the first 3,000 instances of today's `Recon_6.als` (same enumeration order as production): **775 (25.8%)** have an rf edge that reads a state past a newer same-state writer; **125 (4.2%)** of those feed the transmitter's operand. STT_6 and SPT v2 samples: 0.
- After Stage 2 (passes 1-4 run on those 3,000, interleave off, register-level def-use on the concretised program): in **50/3,000** Recon programs the value the transmitter actually reads comes from an ALU op with no load upstream (constants), because the newer writer wins in the program. STT_6: 0/3,000. Those tests carry no secret on the scored path, so any hit on them is a false positive by construction.
- Fix: add the fact verbatim from `STT_6.als:161-170` (P1 / Recon F3 / R-3; manifest E6 already lists it).

### R-4 (I): store shadows

`decode.cc:686-690` (docker tree): `isCondCtrl()` branches and stores are inserted into the shadow tracker; loads become speculative only under a shadow (`:691-693`). Paper §3.1 evaluates "speculation cast by control flow and store instructions". The model's contract is branch-only, so store-shadow leaks are never generated; `proposed/Recon_6_stl.als` is the vehicle. Side effect: a load the model calls non-speculative may be speculative in gem5 (behind a slow store); gem5 is then stricter, so this adds no false positives.

## Question 2: do ALU ops ever sit on a transmitter's operand path?

**Definitive answer.**

- **Eval corpora (two-phase families, the manifest's E1-E11 stimulus): no, for STT_6 and Recon_6, and only as a model artifact for SPT.** In the RI-only cores an ALU between a load and the transmitter is always removable: removing it (RI) bridges the rf hole through the ALU's ddi edge (`fix_rf_hole_p`, e.g. `STT_6.als:218`), so the leak survives and RI-minimality rejects the core. Query Q3 ("some ALU whose output reaches xm's leak operand over rf+ddi and whose input is reached from a load") is **UNSAT on `STT_6_core_ri` at `but 5` (56 s) and `but 6` (exhausted, 768 s)**, and **UNSAT on `Recon_6_core_ri` at `but 5` (177 s)** (the `but 6` run was stopped to free the single Java slot; the bridging argument covers it, since Recon's extra clause is a no-op). Q2 (direct ld -> ALU -> ld-xm) is UNSAT on both cores at `but 4` and `but 5`. Stage 1.5 pins every core rf edge exactly (`stage_seed.py:100-104`) and `one_entering_rf` allows one producer per operand, so it cannot insert an ALU between a core's load and its transmitter operand. Query QS (STT_6 plus the seed of each of the two local STT cores, `testsets/STT_6__twophase_draft/stage1_xml/inst-00000{1,2}`: the Spectre-v1 skeleton with a load and with a `br_x` transmitter) asks for any ALU on a register path from a load into any leak operand of xm, including a second `br_x` operand: **UNSAT for both cores at `exactly 6`** (the seeded model alone is SAT, 3 of 3 requested). These are the RO+RI drafts; the RI-only cores now running on cafe2 were not available locally.
- **SPT_6_oneLP_v2_core_ri: Q2 is SAT at `but 4` and `but 5`.** The witness (S-2 above) keeps the ALU only because of the one-step lag: the branch declassifies the load's value, the lag keeps the ALU's output protected, and removing the ALU would leave the transmitter reading a declassified value. Q2c (same, but the load must really read memory, `Inmem` with its ddi edge) is **UNSAT at `but 5`**: an ALU between a memory-reading load and the transmitter never survives RI-minimality in SPT either, because the producer load's protected `Inmem` keeps the bridged path flagged. gem5-spt would protect this witness (it never declassifies branch predicates, B1); the paper would not.
- **Flat (single-stage) testsets: absent for STT_6 and Recon_6 in the capped enumeration, present for SPT.** Census of the first 3,000 instances (rf-based backward cone of xm's leak operand; program order from spo; `$N` stripped): STT_6 0/3,000 with an ALU on a load-fed path (every transmitter operand rf-fed directly by a load); Recon_6 0/3,000 (32 have an ALU on a br_x's second, constant-derived operand); SPT v2 144/3,000 (48 per transmitter kind), all of them with a load that has no `Inmem` (protected only by the seed; in the program it is a real load from a fresh slot, so the path is real), and SPT pre-v2 72/3,000. Forcing Q2 on the flat models is **SAT for STT_6 (1 s), Recon_6 (2 s) and SPT v2 (7 s)**, so for STT/Recon the absence is the enumeration cap and order (the OTB doc's finding), not the model.
- **After Stage 2.** (a) Eval configs: `runconfigs/fixed_20261030/{STT_6_stt,STT_6_reconmodded,SPT_6_oneLP_fence}_fixed_latest.jsonc` all have `"interleave": {"enabled": false}` (lines 60-61, 60-61, 68-69); no Recon `_fixed_latest` config exists yet (E6 is "to create"). With interleave off, passes 1-4 add no ALU to any transmitter's value path: STT_6 0/3,000, Recon_6 50/3,000 (all the stale-rf artifact R-3, none load-fed), SPT v2 432/3,000 with 144 load-fed (exactly the Alloy-level ones). Pass 5 adds only value-preserving copies on the path: the `br_x` condition pass-through `movq %in,%tmp` (`parsexml.py:2510-2520`) and, in the fp corpus only, the xmm route (`movq`/`movq $0`/`movq`) and the `*_alu` forms (`pxor; por` on the xmm copy, `parsexml.py:2185-2212`), which are the only real ALU ops Stage 2 puts on a path. (b) With interleave on (`STT_6_interleave_reconmodded_fixed.jsonc`: 4 variants, 1 chain of 2-4 steps, kinds other_n/ld/str), over 12,000 programs per model: STT_6 0 load -> ALU -> xm value paths, Recon_6 22, SPT v2 576 (= 4 x 144 base). Chain steps reach the scored value path in 17 (STT), 37 (Recon) and 0 (SPT) programs, always by colliding with a **blank Alloy input slot** (e.g. an Alloy store's unspecified data register picks up a chain load's output, or a stale-rf Alloy ALU's blank operand picks up a chain load).
- **What `pass_interleave` can and cannot do** (`parsexml.py:1255-1430`, pass 3 `:1444-1610`). It inserts chain steps at random positions after the first uncommitted instruction, which includes the non-speculative stretch before the unresolved branch (`:1321-1347`). Chain operands use free-pool registers that are disjoint from the locked Alloy registers (`free_pool = virtual_pool[3:]`, `virtual_pool = reg_order[n_locked:]`, `:1535-1547`) and memory slots after the locked ones (`:1572-1578`). So it **cannot** feed the transmitter's operand (always a locked register), cannot insert itself between an Alloy producer and consumer, and cannot touch Alloy memory. It **can** feed a blank input slot of an Alloy instruction; that puts a chain value on the transmitter path only if that Alloy instruction is already on the path (an Alloy ALU with a blank second operand, or a store with a blank data register). In STT/Recon RI cores no ALU is on the path, so interleave as written cannot manufacture the OTB merge from the eval corpus. The OTB decision in `URGENT_TODO.md` (options a/b/c) stands; option (c), forcing an ALU in Stage 1.5, would need the core's direct rf edge relaxed, because the seed pins it.

## Question 3: does Stage-2 insertion change protection? Rules for a fanout generator

Terms: **path value** = any value in the rf+ddi backward cone of xm's leak operand, plus anything computed from one. **Pre-window** = program positions before the first unresolved Alloy branch (committed or not); these instructions are non-speculative. **Inserted** = anything not in the Alloy instance (interleave chains, fillers, fp/xmm routing, infrastructure).

**Measured today (interleave config above, 12,000 programs each).** Pre-window chain loads/stores whose address register was last written by an Alloy instruction that reads a locked register: STT_6 23, Recon_6 12, SPT v2 39. The producers are Alloy ops whose outreg is blank (so it lands in the free pool): `add` (lea), `bitnot`, `zsm`, `div`, `load`. Example `SPT v2 inst-000566_v0`: Alloy `ld -> rax` (the path value), Alloy `zsm r14 = rax * r11` (blank outreg), then a pre-window chain store with address `r14`. Under gem5-spt this declassifies r14 only (imul has no backward rule, S-5), so the path value stays protected; under the paper's algebra an invertible op (`add`/`not`/`xor` with a public operand) would also untaint rax. No inserted instruction today reads a locked register directly.

**Rules for all three defenses**

1. Never write a locked (Alloy) register or an Alloy memory slot, except a value-preserving copy of the same value (the fp route). Pass 3 already guarantees this for chains.
2. Never read or write an Alloy memory slot from an inserted load or store (keeps Recon_6's location semantics and SPT's STL rule out of play). Pass 3 guarantees it today.
3. Never insert a branch before or inside the Alloy region: it changes which Alloy instructions are speculative (the contract) or cuts the window. Inserted branches after the transmitter are harmless.
4. In-window insertions may read path values freely; they are just more speculative instructions, and none of the three defenses untaints anything at a speculative instruction.
5. Inserted ALU ops on the path (fed from a path value, feeding an Alloy blank slot on the path) are safe: STT, ReCon and SPT all propagate taint as "any tainted input taints the output" (SPT p612 §6.3, `rob_impl.hh:236-249`; Recon `taint_tracker.cc:108-131`). They are the OTB target (R-SA-8). Exception: never overwrite a path register with an immediate (SPT untaints load-immediates, p612 §6.5).
6. Keep infrastructure out of locked registers (the reserved vpool scratch/cond/probe registers, `parsexml.py:1416-1421`) and avoid LLVM spills of path registers; a spill/reload pair is an inserted store/load on the path.

**SPT (E11)**

7. No pre-window inserted load or store whose address register holds a path value, or a value from which a path value is invertibly computable with otherwise public inputs (`mov`, `add`/`sub`/`lea`, `not`, `xor`, `neg`). Under gem5-spt only the same physical register, plus `mov` and `add/sub/adc/sbb` microops, matter (`rob_impl.hh:853-880`); the paper's rule is "invertible arithmetic" (p613 §6.6), so the generator should use the broader invertible list. Today's free-pool rule satisfies the gem5 version but not the paper version (the 39 cases above, if their producer is `add`/`bitnot`).
8. No pre-window inserted branch whose predicate is a path value (paper declassifies branch predicates, p612 §6.3; gem5 doesn't, B1, so this rule is for paper fidelity only).
9. Simplest generator rule that satisfies 7 and 8: a pre-window inserted instruction may read only registers written by other inserted instructions or initialised constants, never a register last written by an Alloy instruction.
10. If the vocabulary grows register `add`/`sub`/`mov` (VOCAB_TABLES), rule 7 becomes live under gem5 too.

**ReCon (E6) and STT**

11. With classic caches the reveal is dead (R-SA-1), so the only untaint is STT's (taint root reaches its VP). No insertion that respects rules 1-3 can untaint a path value. Inserted stores with slow addresses add store shadows (`decode.cc:688-689`), which only makes gem5 stricter (possible false negatives, never false positives); keep inserted store addresses fast if the window matters.
12. If the reveal is ever active (`--ruby` or a fixed build): no pre-window inserted load whose address register is directly the destination register of a load (Alloy or inserted). That is a direct load pair, which reveals LD1's word at LD2's commit (§4.3, §5.1). Under today's location-based Recon_6 this cannot legitimise a model-flagged leak (an Alloy non-speculative load already makes its location public in the model, and rule 2 keeps inserted loads off Alloy memory), but it can once R-1 is fixed.
13. fp/xmm routing is safe for meaning on all three: it preserves value and taint and breaks load pairs (intervening `mov2fp`/`limm`/`mov2int`). The hits it finds (STT S1 xmm4, Recon R-SA-12/13) are gem5 bugs, which is the point.

## Decisions for Anna

1. **DECIDE: fix S-1 (v2-4 makes SPT declassification dead) before Stage 1.5 of SPT runs?** Context: v2 is approved and its Stage 1 is running on cafe2; Stage 1.5 is not built. Options: (a) Option A diff above (declassify the transmitted value plus its load's memory read), with Q1 UNSAT and the v2 differential as validation, then re-run SPT Stage 1; (b) Option B (drop the transitive term, fix P3), the principled fix, bigger validation; (c) keep v2 and bucket the "declassified same value" hits with a diagnostic. Evidence: Q1 SAT on v2, UNSAT on pre-v2; gem5 untaints at the VP (`lsq_unit_impl.hh:1189-1209`). **Recommendation: (a) now, (b) later.** (a) is one line in clause 2, keeps "superset of SPT" and restores the case that makes SPT different from STT. (c) is acceptable only if the SPT Stage-1 run cannot be repeated.
2. **DECIDE: location-based vs instance-based protection for Recon_6 (and STT_6).** Options: (a) instance-based (protect speculative loads' outputs; sketch in R-1), matching the paper and the build; (b) keep location-based and state it as a deliberate value-level scope (ReCon §3.1 "Register Protection"); (c) defer until ReCon can actually reveal. Evidence: QR1a UNSAT / QR1c SAT on both models. **Recommendation: (a) for STT_6 and Recon_6 together in the regen Anna already plans** (two-stage regen), because it is the only unsound clause found and it hides tests that plain STT must block on every STT-family build.
3. **DECIDE: add `rf_from_most_recent_writer` to Recon_6 (and re-derive `Recon_6_core_ri`) before the Recon Stage 1 results are used.** Evidence: R-3 (25.8% stale rf; 50/3,000 programs score a constant-derived value). **Recommendation: yes, now;** the running cafe2 Recon core run inherits the gap.
4. **DECIDE: the generator rule for SPT (rule 7/9): paper-level invertibility or gem5-level microop names?** Options: (a) rule 9 (pre-window inserted instructions never read Alloy-written registers), simplest and safe for both; (b) allow reads but forbid invertible producers (paper list); (c) gem5 list only. **Recommendation: (a).**
5. **DECIDE: OTB from Stage 2.** Measured: interleave cannot put an ALU on the transmitter path of an STT/Recon RI core (no ALU there to hook, transmitter operand is locked). Options: (a) bugsynth forced OTB model (`STT_6_otb2`) plus interleave, as `URGENT_TODO.md` already recommends; (b) let fanout v2 draw a chain input from the locked register of the path load and write an inserted ALU result into a *new* register that an inserted (in-window) transmitter reads, i.e. build the OTB merge entirely from inserted instructions in the window (safe by rule 4/5); (c) relax the Stage 1.5 seed to allow inserting an ALU on the core's xm edge. **Recommendation: (a) for the eval, (b) for fanout v2.**
6. Lower priority, record only: S-3 (STLPublic gate) and the Recon reveal rewrite (R-2) matter only after the transitive term is removed (S-1 option B) or the reveal works in gem5.

## Queries run (re-runnable)

Harness: copy the model to a scratch folder, conjoin `q` into the first `run gen_lit` (or replace `gen_useful_litmus` by `q` alone for "facts only"), append the predicate, run `java -Xmx4g -cp alloy6.jar:. a6CountModels <copy.als> <out> <limit>` from `STAGE1_alloy/` with Java 17, under `gtimeout`. One Java process at a time; the simspect-c8 "lost" differential was also running on the Mac. "Total models: 0" with rc 0 = exhausted (UNSAT at that scope).

| ID | Model | Form, scope | Result |
|---|---|---|---|
| Q1 | SPT_6_oneLP_v2 | with gen_useful_litmus, exactly 6 | SAT (7 s) |
| Q1 | SPT_6_oneLP (pre-v2) | same | UNSAT (20 s) |
| Q2 | STT_6 / Recon_6 / SPT v2 flat | with gen, exactly 6 | SAT / SAT / SAT (1 / 2 / 7 s) |
| Q2 | STT_6_core_ri | but 4, but 5 | UNSAT, UNSAT |
| Q2 | Recon_6_core_ri | but 4, but 5 | UNSAT, UNSAT |
| Q2 | SPT_6_oneLP_v2_core_ri | but 4, but 5 | SAT, SAT |
| Q3 | STT_6_core_ri | but 5, but 6 | UNSAT (56 s), UNSAT (768 s) |
| Q3 | Recon_6_core_ri | but 5 (but 6 stopped) | UNSAT (177 s) |
| QR1a | Recon_6 / STT_6 | facts only, exactly 6 | UNSAT / UNSAT |
| QR1c | Recon_6 / STT_6 | facts only, exactly 6 | SAT / SAT |
| QR1a, QR1c | Recon_6 / STT_6 | with gen | all UNSAT (RS-minimality; see R-1) |
| QR2 | Recon_6 | facts only, exactly 6 | UNSAT (823 s) |
| Q2c | SPT_6_oneLP_v2_core_ri | but 5 | UNSAT (11 s) |
| QS | STT_6 + seed of `testsets/STT_6__twophase_draft/stage1_xml/inst-00000{1,2}` | with gen, exactly 6 | UNSAT / UNSAT (seed alone: SAT) |

```alloy
// Q1 (SPT): declassified value re-flagged
pred q { some prod: Loads, a2, a3: Inaddr |
  a2 in nonspeculative_xmit_p[no_p] and a3 in speculative_xmit_p[no_p] and a3 in xm.operands and
  a2 in prod.outreg.rf and a3 in prod.outreg.rf and a3 not in last_committed_protset_p[no_p] }

// Q2: load -> ALU -> load-transmitter address
pred q { some l: Loads, o: (Otherns + Otherxs), x: xm & Loads |
  some (l.outreg.rf & o.inreg) and (o.inreg & l.outreg.rf) -> o.outreg in ddi and some (o.outreg.rf & x.inaddr) }
// Q2c: Q2 plus  some l.inmem and l.inmem -> l.outreg in ddi

// Q3: any ALU on a load-fed path into xm's leak operand (rf+ddi, any xm kind)
pred q { some o: (Otherns + Otherxs) |
  some (o.outreg.^(rf + ddi) & leakage_function & xm.operands) and some (o.inreg & (Loads.outreg).^(rf + ddi)) }

// QR1a (QR1c: replace = by != in the opstate line)
pred q { some disj l1, l3: Loads |
  l1 not in speculation_contract_p[no_p] and l3 in speculation_contract_p[no_p] and
  some l1.inmem and l1.inmem.opstate = l3.inmem.opstate and
  no (l1.outreg.rf & Loads.inaddr) and no rf.(l3.inmem) and l3.inmem -> l3.outreg in ddi and
  xm in Loads and some (l3.outreg.rf & xm.inaddr) }

// QR2: reveal not implied by the STT fold, under no_p and every perturbation gen_lit uses
pred rdiff[p: PTag->univ] { some (Mem_s - hardware_protection_policy[p]) - (Loads & no_unresolved_brs_bf_or_is_p[p]).inmem.opstate }
pred q { rdiff[no_p] or (some i: Instruction | rdiff[RR->i]) or rdiff[RC->first_uncommitted + RR->first_uncommitted] or (some s: State | rdiff[RS->s]) }

// QS: seed_core (from STAGE1_alloy/stage_seed.py on the core .txt) and
//   some l: Loads, o: (Otherns + Otherxs) | some (l.outreg.rf & o.inreg) and
//   (o.inreg & l.outreg.rf) -> o.outreg in ddi and some (o.outreg.rf & leakage_function & xm.operands)
```

**Censuses (Python, read-only).** Instance census: parse each `inst-*.txt` (Alloy `toString` dump), program order from `spo`, backward cone of xm's leak operand over `rf`+`ddi`, stale rf = an rf edge with a same-state writer strictly between producer and consumer in spo. Samples: first 3,000 instances of `STT_6.als` and `Recon_6.als` enumerated locally with `a6CountModels` (same order as production), and `results/spt_v2_20261108/xml_v2` / `xml_orig` (3,000 each). Post-Stage-2 census: import `STAGE2_compilation/parsexml.py`, run passes 1, 2, 2.5, interleave, 3 exactly as `batch_generate.run_pipeline` does (same per-variant seeds, mode `mispredict_not_taken`), then a register/memory def-use trace on the concretised instruction list; "value path" follows loads only through memory (not their address register). Scripts (census, post-Stage-2 tracer, query builder `mkq.py`, runner `runq.sh`, each with a usage header) and every `.als` query copy used above are in `STAGE3_gem5/triage/model_audit_20261108/` (query copies under `queries/`, see its `README.txt`).
