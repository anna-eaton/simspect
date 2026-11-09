# diag_speclfb_walk_order: SpecLFB walk-order (known cause, verdict pending)

**Issue and signature.** The ROB sees a load one cycle before the LQ (`renameToROBDelay=1` < `renameToIEWDelay=2`) and the sticky `PrevNoUnsafe` is never cleared, so a rank>=1 speculative load is marked safe and fills. The diagnostic buckets a hit when the faithful rerun's only req=ld cause tag is `walk_order`.

**Evidence.** AMULET_BUGS_DETECTION_ACCOUNTING.md §2 walk-order row and §4; evidence file `speclfb_evidence.json`.

**Verdict.** Known cause; whether it is UV6 with a wider scope or a separate bug is Anna's DECIDE. `PHASE = "known_pending"`, so these hits never land in NEW and are not counted as found. Scope: every SpecLFB campaign (E14).
