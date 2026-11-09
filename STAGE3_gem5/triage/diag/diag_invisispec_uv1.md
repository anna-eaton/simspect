# diag_invisispec_uv1: UV1, a speculative load evicts an L1D line (real gem5 bug, known, AMuLeT)

**Issue and signature.** The InvisiSpec build lets a speculative load's fill evict a live L1D line (`L1D:evict req=specld`, with the `L2:coh` PUTX writeback); it disappears with `--apply-spec-eviction-patch`. The diagnostic buckets a hit when the faithful rerun's own hit record has at least one such eviction and every other offending event is a known kind: the `L2:coh req=wb` writeback, D-1 DTLB replacement touches, or (Futuristic only) store-actor events. Any other event, such as an L1D fill by a speculative load or an event whose seq has no fetch record, leaves the hit NEW.

**Evidence.** `wiki/findings/mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md` §2 (UV1 row: 2995/3000 STT_6 tests). Evidence file `invisispec_evidence.json` (`rerun_hits_evidence.py --analyzer invisispec`).

**Verdict.** Real gem5 defense bug, known (AMuLeT UV1). Scope: build-specific, every InvisiSpec campaign (E12a, E12b).

**Rerun caveat (2026-11-09).** The Ruby InvisiSpec reruns are not bit-identical to the campaign runs: for E12a fv2fp inst-042604 the campaign record has 196 hook events and the rerun has 207, reproducibly. So the diagnostic classifies the rerun's own hit record against the rerun's own trace, and only when the rerun hits with the campaign's offending (struct, kinds) signature (`same_signature`).

**Allowed co-events (revised 2026-11-09 after the fv2 2% reruns).** Store-actor events are allowed on both schemes, because E12b (Spectre) shows them too: 788 of its fv2 hits had uv1 + wb + d1 + store. DTLB `repl_touch` events count as D-1 whatever the micro-op, because seqs with no fetch record are non-first micro-ops of a macro-op.
