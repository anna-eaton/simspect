# diag_speclfb_nonload_footprint: SpecLFB footprint made only by non-load requests (out of scope)

**Issue and signature.** None of the hit's in-window footprint events (faithful rerun, `speclfb_analyze.py` cause tags) has `req=ld`; they come from stores, instruction fetch or writebacks. SpecLFB protects only speculative loads' L1D/L2 presence, and the 2026-11-07 SpecLFB triage dropped non-load events the same way (`helpers/triage.py`; `classify_hits.py` reports `disq_non_load_footprint`).

**Evidence.** Scope list in `wiki/findings/mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md` (SpecLFB: L1D + L2 presence, §1 p632, §7 p640). Evidence file `speclfb_evidence.json` (`rerun_hits_evidence.py --analyzer speclfb`).

**Verdict.** Not a leak SpecLFB promises to stop (disqualifier). Scope: every SpecLFB campaign (E14).
