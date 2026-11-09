# diag_invisispec_d1_dtlb: D-1, DTLB replacement touch on a speculative hit (known deviation)

**Issue and signature.** `arch/x86/tlb.cc` updates `lruSeq` on every DTLB hit, including speculative ones, while the paper delays D-TLB replacement updates to the visibility point (§VI-E3). The diagnostic buckets a hit when every offending event in the faithful rerun is a DTLB `repl_touch` by a non-store seq (or, on Futuristic, a store-actor event), with at least one such touch.

**Evidence.** `wiki/findings/audits/2026-10-28/invisispec_flagged_events_triage.md` §1 (REAL deviation, known gap; recommended as its own bucket); SOURCE_AUDIT_INVISISPEC.md lists D-1 as "known and not counted"; AMULET_BUGS_DETECTION_ACCOUNTING.md §4 "bucketed separately (D-1)". The touched entry is the stack page, which committed code also touches, so it becomes observable only after a later TLB eviction.

**Verdict.** Real implementation deviation, already known (not a new bug). Scope: every InvisiSpec campaign (E12a, E12b).
