# Defense scoping vs implementation bugs: which AMuLeT findings we catch

**For:** Anna · **Written:** 2026-10-28 · **Decision (Anna, 2026-10-28):** a leak through a structure or channel that the defense's own paper leaves out of its protection is a **scoping problem of the defense mechanism**, not an implementation bug. SimSpect mentions it but does not try to catch it. SimSpect catches **implementation bugs**: places where the build fails to protect something its paper promises. unXpec is out of scope for now. Sources: the papers in `~/Documents/quail/sources/papers/` (page numbers below), quoted via `FOOTPRINT_DEFENSES_PAPER_AUDIT.md` except where marked as read directly for this doc. The structure-by-structure table with build citations is `PROTECTION_SCOPE_TABLE.md`.

## The rule

Each defense's transmission criterion (`specs/leakage/<defense>.json`) observes exactly the structures its paper promises to protect. A finding is:

- **In scope (implementation bug):** the paper promises to protect structure S against channel C, and the build leaks through S via C. The criterion must catch it.
- **Out of scope (scoping problem):** the paper explicitly excludes S or C, or says it doesn't describe protecting it. The leak is real, but it is a limit of the mechanism as designed. We record it in the criterion's `out_of_scope` list with the quote. It's worth a sentence in the paper ("our criterion follows each defense's stated contract; these are contract gaps"), but it is not a detection target.

## Classification of the AMuLeT findings

| finding | defense | what leaks | paper says | verdict |
|---|---|---|---|---|
| UV1 | InvisiSpec | speculative miss evicts a live L1D line | protects every data-cache level, presence + replacement (§III-B p3) | **in scope, implementation bug** |
| UV2 | InvisiSpec | MSHR/TBE contention | "contention on other resources, such as MSHRs or execution units, could slow down the receiver, but such side channels are considered out of scope in this paper" (§VII, original p10) | **out of scope (scoping)** |
| KV1 | InvisiSpec | wrong-path I-fetch installs L1I line | "For simplicity, we do not describe the protection of the instruction cache or instruction TLB" (fn. 2 p3) | **out of scope (scoping)** |
| UV6 | SpecLFB | first unsafe speculative load not held in LFB, fills L1D | protects unsafe loads that miss, L1D + L2 in gem5 (p632, p640) | **in scope, implementation bug** |
| UV4 | CleanupSpec | line-crossing load installs 2 lines, 0 cleanup | cache state after cleanup "is as if the transient loads did not access the cache" (p2) | **in scope, implementation bug** |
| UV5 | CleanupSpec | over-clean of a committed line | correct-path changes "need to be preserved and not reversed" (p7) | **in scope, implementation bug** |
| UV3 | CleanupSpec | speculative store not cleaned | RFOs "issued non-speculatively" (§4(a) p8), so stores should never change cache state | **in scope**, but not reachable on our build: squashed stores never touch the cache here |
| unXpec (KV2) | CleanupSpec | cleanup latency depends on hit/miss | cleanup "does not practically leak", constant-time left to "future work" (§4(b) p8); AMuLeT saw it through L1I tags, and I-cache is out of scope (p1 fn.) | **out of scope for now** (Anna) |
| KV3 | STT | wrong-path store translates and fills the D-TLB | see below | **out of scope (scoping)**, with one caveat |

## STT and stores (KV3)

Read directly from `yu-2019-stt.pdf` for this doc:

- p5: "Classifying only loads as transmitters will block memory system-related explicit covert channels. … We assume that stores trigger a cache coherence invalidation only on retirement, or else are defined as transmitters."
- p10: "In isolation, a store creates neither explicit or implicit channels because we assume stores are performed at retirement."

So STT's mechanism assumes stores have no speculative footprint, and protects only load transmitters. A speculative store that touches the D-TLB at execute falls outside that assumption. That is a scoping problem of STT.

**Caveat:** the p5 sentence has an "or else": if stores *do* act before retirement, they must be classified as transmitters. Someone could read that as a requirement on implementations, which would make KV3 an implementation bug. Against that reading, the sentence names cache coherence invalidation, not the TLB. And `wiki/findings/bug/STT_KV3_TLB_REVIEW.md` currently calls KV3 "a real STT defense-scope bug", so that doc's wording needs to be brought in line with whichever reading you pick. I'd go with scoping, citing p10, and note the p5 clause.

## Consequences

- **Criteria:** the InvisiSpec criterion does not observe MSHRs, L1I or I-TLB. The CleanupSpec criterion does not observe L1I or cleanup timing. The SpecLFB criterion does not observe hits or replacement metadata (§9 p643). Each exclusion is listed in `out_of_scope` with its quote.
- **Hooks still export everything** (all cache levels, MSHRs, L1I, TLBs) to the pipeline trace, so an out-of-scope leak can still be *shown* when we want to discuss it. Only the predicate is limited.
- **The detection score to report** is in-scope implementation bugs: UV1, UV6, UV4, UV5 (+ UV3 as unreachable on this build). UV2, KV1, KV3 and unXpec are discussed as contract gaps.
- **Docs to update once agreed:** `AMULET_BUGS_DETECTION_ACCOUNTING.md` (bug scoring), `STT_KV3_TLB_REVIEW.md` (bug → scoping), `AMULET_THREE_DEFENSES_EXPLAINER.md` scorecard.

## Spectre vs Futuristic mode (InvisiSpec), for reference

From `yan-2018-invisispec.pdf` (read directly for this doc):

- **Spectre:** "USLs are the speculative loads that follow an unresolved control-flow instruction. As soon as the control-flow instruction resolves, the USLs that follow it in the correct path … transition to safe loads" (§IV-A1 p4). This is STT's Spectre visibility point (STT p5).
- **Futuristic:** "USLs are all the speculative loads that can be squashed by an earlier instruction." A USL becomes safe only when "(i) it is not speculative anymore because it is at the head of the ROB, or (ii) it is still speculative but cannot be squashed by any of the squashing events in Table I for Futuristic". Table I lists exceptions, control-flow mispredictions, load–store and load–load address aliasing, consistency violations, and interrupts.

So Futuristic is *almost* "anything not yet committed". A load is unsafe until it reaches the ROB head, unless every older instruction is already known not to squash it. STT has the same split (p5: "In the Futuristic model, an instruction has only reached this point if it cannot be squashed"). AMuLeT ran InvisiSpec and STT in Futuristic mode (AMuLeT §4.1 p8).

**What that does to our modeling.** Under Futuristic, the model's *speculation* half (which instructions are speculative, the `has_unresolved_brs_p` contract at `STT_6.als:325`) collapses to "uncommitted", so that part does little. What still matters is the *test-shape* half: what gadgets get generated and what feeds the transmitter. For the footprint defenses, the paper audit found that this is also where STT_6 is narrow: it requires a taint chain from a speculative load, so it never produces single-load or register-secret gadgets (`FOOTPRINT_DEFENSES_PAPER_AUDIT.md` §5).

**On the checker side, Futuristic gives us a cleaner window.** InvisiSpec's own expose/validate event marks each load's visibility point, and the hooks emit it, so the criterion becomes "footprint caused by load i before i's expose/validate (or retire)". That is the defense's own notion of when i is safe, not our branch window.
