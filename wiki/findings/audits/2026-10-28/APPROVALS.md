# Changes awaiting Anna's approval (from the 2026-10-28 audit sweep)

Each item names its change, why it is needed, and the evidence file. Nothing here has been applied. Alloy fixes were found by reading the models, not by running Alloy, so each one is validated SAT/UNSAT on a scratch copy before it touches a real `.als`. Answer per item: approve / reject / discuss.

## A. Alloy model changes (`.als`, per-change sign-off)

### A-STT: `STT_6.als` (evidence: `alloy_STT_6.md`)

- **STT-1, store address as an implicit-branch transmitter (high, coverage).** STT p5 and p8 §6.4.2 treat store-to-load forwarding as an implicit branch: a younger load's forward-vs-cache decision reveals an older store's address. The model has no such transmitter. Proposed: `leakage_function = Loads.inaddr + Branchxs.inreg + (Stores & (^spo).Loads).inaddr`, plus a checker keyed on the younger load's forward-vs-cache fate. This overlaps the untracked `STT_6_stl.als`, so decide whether that file is the vehicle.
- **STT-2, let the transmitting branch be mispredicted (medium, coverage).** Minimality at `:306` forces every xmit branch to be resolved, so the resolution-based channel (STT p7 §6.4) is never exercised. Proposed: exempt `xm & Branchxs` from the RR clause. **Prerequisite:** the `parsexml.py` duplicate-PC NOP fix from `DESIGN.md` must land first, because this turns that path on.
- **STT-3, untaint per load instance, not per memory location (medium, coverage).** `:331` removes a *State*, so a later unsafe load of the same location counts as untainted, while STT says an unsafe load's output is always tainted (p6). Proposed: seed taint from unsafe-load outputs (`taint_src_p = (Loads & has_unresolved_brs_p).outreg`), optionally add `Inaddr->Outreg` to `ld_ddi`, and re-validate RS-minimality. The Recon audit's F2 is the same issue, so they share one fix.
- **STT-4, remove label duplication (low, budget).** `fact no_otherx {no Otherxs}` (Otherx never transmits, so each `other` doubles the enumeration). `fact {no Branchns.inreg}` (STT protects every explicit branch).
- **STT-5, cleanup (low, no semantic change).** Delete or comment the vacuous conjuncts at `:263` and `:271`. Fix `no_unresolved_mem_p` (`:258-260`) to use the `_p` relations. Fix the comments.

### A-SPT: `SPT_6_oneLP.als` (evidence: `alloy_SPT_6_oneLP.md`)

- **SPT-1, final check re-taints what untaint removed (high, false positives).** The `P.^(op_edges_p)` term at `:259/271/280` cancels the store-to-load untaint at `:357`, because a store's `Outmem` is never untainted. Proposed: (a) drop the `^op_edges` term, or (b) add "store Outmem untainted when its data inregs are untainted", gated on STLPublic (SPT-3).
- **SPT-2, backward untaint follows the paper's rules only (high, coverage).** `:349` untaints the whole backward cone. The paper (p7) allows only MOV (output untainted → input untainted) and invertible-ALU (output plus all but one input untainted → the last input untainted). Across memory, untaint applies only when the load's output is untainted, under STLPublic. Proposed: replace the cone with those per-instruction rules. This is how gem5-spt over-eager untaint bugs become detectable.
- **SPT-3, STLPublic gate on store-to-load untaint (medium-high, coverage).** `:357` is the naive rule that the paper's Fig. 5 says leaks. Proposed: require the store and load addresses untainted and no older store with a tainted address in between.
- **SPT-4, make `ddi` edges mandatory (medium).** `:155` and `:161-164` only upper-bound `ddi`, so the same program can be judged both ways. Proposed: a `fact ddi_complete` with `inmem→outreg` and `inreg→outreg/outmem` per allowed kind.
- **SPT-5, untaint to a fixpoint (medium, false positives).** There is one spo-order pass (`:225-236`), but the paper (p7) untaints older and younger instructions over several cycles. Proposed: run the 6-deep sweep 3 times.
- **SPT-6, a non-speculative conditional `Branchn` declassifies its predicate (medium, false positives).** Proposed: add a separate declassify set that includes `Branchns.inreg`, or forbid `inreg` on `Branchn`.
- **SPT-7/8 (low).** `fact {no Otherxs}`. Fix `no_unresolved_mem_p` to use the `_p` relations. Remove dead code and stale comments.
- Suggested batching from the audit: SPT-1 + SPT-4 go in one regen with A1/A2. SPT-5 and SPT-6 are cheap. SPT-2 and SPT-3 are a design question: does the SPT oracle follow the paper's untaint algebra exactly? If yes, both are required.

### A-Recon: `Recon_6.als` and `STT_6_multisource.als` (evidence: `alloy_Recon_6.md`)

- **R-1, Recon_6's reveal policy is a no-op (critical).** `:316-318` removes only states that the STT fold at `:323` already removes, so Recon_6 ≡ STT_6 without A2. No test exercises ReCon's reveal. **Decision needed now, even before a fix:** treat Recon_6 results as STT-minus-A2, so Recon-vs-STT differences are not model signal. Confirm first with a forcing-predicate SAT check.
- **R-2, rewrite the ReCon reveal to match the paper.** This needs three parts together: a reveal on a direct load pair at LD2 commit (§4.3, §5.1.1, §5.2; the single-hop `revealed_p` is in the audit), a conceal when a store to the same word commits (§5.2), and instance-based untaint (STT-3).
- **R-3, add A2's `rf_from_most_recent_writer` to Recon_6 (high).** It is missing (STT_6 has it at `:161-169`).
- **R-4, fix boundary clause (c) in `STT_6_multisource.als` `:323` before generating the OTB testset (high).** As written, it still excludes the two-branch getOldestTaint gadget (expected UNSAT) and makes the relaxed clause redundant. Proposed: `secure[RC->first_uncommitted + RR->unresolved]`, or require `first_uncommitted` to be an unresolved branch, keeping per-branch contribution minimality. Confirm UNSAT first.
- **R-5 (medium, check first).** The speculation contract is branch-only, while ReCon's evaluation also uses store speculation (§3.1). Check which speculation sources the gem5-recon runs actually use before changing anything.

## B. Concretization change (`parsexml.py`, needs sign-off; evidence: `testset_reachability.md`)

The prologue writes every byte of the ~2 KB data footprint, which sits within 1–2 pages, and the secret is almost always 0. So the L2/directory miss terms, the D-TLB terms, the coherence-change terms and split-load (UV4) terms of the footprint criteria can never fire, and L1D misses happen only by accident. Proposed options, any subset:

- **B-1:** leave the speculative-target line cold (don't pre-write it, or flush it with `clflush` after the prologue).
- **B-2:** a probe stride of 64 B. This makes the `:2003` comment true: one line per secret value, which is how the secret value becomes observable.
- **B-3:** an eviction-set prologue that fills the target set with 512 B-stride committed lines, so a speculative fill evicts a committed victim (CleanupSpec d_victim, InvisiSpec UV1).
- **B-4:** a line-straddling slot, for split loads (UV4).
- **B-5:** a second page, for D-TLB terms.
- **B-0, read-only, no approval needed:** first count how many existing tests have a speculative L1D miss, which tells us how much B-1..B-5 matter.

This is a coverage change, not tuning to specific bugs, but it changes every footprint testset. The flag would be off by default for the other defenses.

## C. Checker semantics (`check_footprint.py`; evidence: `check_footprint_review.md`, `invisispec_flagged_events_triage.md`)

- **C-1:** events in the window that can't be tied to an instruction (`seq=-`) make the record **undecided**, not no-leak. An eviction with `seq=-` falls back to the fill that caused it. **Recommend yes.** This is the "never hide a possible leak" rule.
- **C-2:** the window gates **the actor's issue**, not each event's tick, so a squashed load's late fill still counts for InvisiSpec and SpecLFB. **Recommend yes.**
- **C-3:** actors are **loads only** (stores' D-TLB effects are outside the papers' protection: InvisiSpec USLs are loads, and STT p10 assumes stores perform at retirement). **Recommend yes.**
- **C-4:** a missing pipeview record → undecided, instead of treating the visibility point as never reached. **Recommend yes.**
- **C-5:** CleanupSpec counts late installs by in-flight squashed loads that land after the squash (paper p6 says those should never install). **Recommend yes**, since it's the paper's own promise.
- *No approval needed (a plain bug):* the churn bookkeeping fix, which pops the stale live entry on every evict and invalidation.

## D. Scope decisions still open

- **D-1:** should InvisiSpec's D-TLB replacement-on-hit events (a real deviation, `tlb.cc:146-150` vs §VI-E3) get their own known-artifact bucket, so they don't drown new findings? **Recommend yes.**
- **D-2:** should CleanupSpec's criterion add the directory's I→E and sharer changes, which the paper (p7) says are "allowed and reversed"? That is a reversal promise, but nothing checks it today.
- **D-3:** should InvisiSpec's criterion add page-table access/dirty bits from the D-TLB hit case (pp9-10)? The hooks don't emit them yet.
- **D-4:** KV3 (STT store → D-TLB). Is it scoping (STT p10) or an implementation bug (the "or else are defined as transmitters" clause on p5)? I recommend scoping.

## E. Hook fixes (gem5 print hooks only; I'll do these unless you object)

- **CleanupSpec:** dedupe the L2 skip on re-queue, print the C_ISS/M_I ack transitions, emit `cleanup_restore` on completion instead of request, tag restore-forced evictions with `sq`, map `DropIncomingPacket*`, emit `cleanup_done` for squashes with no buffered loads.
- **InvisiSpec:** suppress the SB fill after a squash, release the second line of a split load, clear stale pending-fill causes, label a wrong-L1 removal as `inv`, give each message its own attribution context.
- Both need a rebuild. The pre-hook binaries stay backed up.

## F. Run-config and spec values

- **F-1:** footprint reruns are **loads only** (implement the ignored `filter.xmit_kind`). **Recommend yes.**
- **F-2:** L1D 1kB/2-way (ours) or 8kB/2-way (AMuLeT's amplified setting)?
- **F-3:** TBEs 2 (the Ruby default, which is AMuLeT's amplified setting) or 256?
- **F-4:** InvisiSpec `needsTSO=1 --allowSpecBuffHit=1` (ours) vs `needsTSO=0` without buffer hits (AMuLeT's)?
- **F-5:** the CleanupSpec rerun injects the 5000-cycle stall; the old residue run didn't. Keep it?
- **F-6:** `specs/timing/*.json` say `fnc_commit_stall_cycles: 30`, but every campaign used 150. Set them to 150?
- **F-7:** add `--freeParam=3` to `runconfigs/run_config_SPT_6_*` (the fence campaign already has it).
- **F-8:** add `--ruby` to the SPT InvisibleSpec configs (likely the same no-`--ruby` bug).
- **F-9:** run one recon test to confirm `--scheme` actually applies (the `Simulation.py:466` type check). Read-only, no approval needed; flagged because it may invalidate Recon/STT-on-recon results.
- **F-10, after B/C:** the hook naming (`L1IMSHR`, `L2MSHR`, `DIRTBE`, `LLCSB`, `line=-`) and TLB events carrying the virtual page. Approve as is?

## No approval needed (doc and record fixes, will just do)

`ALLOY_MODEL_CHANGES.md` (A2 is already in STT_6; A1 doesn't apply to STT_6; the SPT scope statement), `AMULET_BUGS_DETECTION_ACCOUNTING.md` (unXpec description, scoping verdicts), `STT_KV3_TLB_REVIEW.md` wording after D-4, the SpecLFB quote and InvisiSpec quote order in the criterion JSONs, hard-wrap fixes in `COMMANDS.md` and `gem5-hooks/README.md`, and checking whether the swept STT_6 testset predates commit `e298a9e`.
