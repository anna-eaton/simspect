# diag_dom_xmit_store_forward: DoM transmitter served by store forwarding (criterion pending, R-SA-18 / Q6)

**Issue and signature.** On DoM (gem5-recon-modded scheme 3), every in-window record of the test has `cache_fate=store_forward` and `data_obtained=true`: the transmitter got its data from the store queue and made no cache access. DoM only delays speculative L1 misses, so this is allowed by design. `check_ld`'s data-obtained gate (specs/leakage/recon.json) still scores it as a leak. Pure raw-record check on the campaign's own `_sweep_raw`; no rerun.

**Evidence.** In the 2% fanout-v2 sample every E9 ld hit (2602 in both testsets) is store_forward, and the same 2602 tests hit on E1 Unsafe, so DoM never changes the outcome. The transmitter addresses land on prologue-zeroed stack slots that are still in the store queue (SOURCE_AUDIT_RECON.md R-SA-13 'gem5 check').

**Verdict.** Not a DoM defect: it is a leak-criterion question (R-SA-18 DoM half / Q6, URGENT_TODO DoM DECIDE). `PHASE = "known_pending"`, so these hits never land in NEW but are not called real bugs either. Scope: DoM campaigns only (`E9_STT_6_fv2`, `E9_STT_6_fv2fp`). Never on STT/NDA rows: there a forwarded transmitter still means its tainted or unsafe address operand got through.
