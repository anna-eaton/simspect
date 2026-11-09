# diag_recon_sse_load_producer: R-SA-13, FP/SSE loads are never speculative on the Recon-group builds (real gem5 bug, known)

**Issue and signature.** In `decode.cc:684-695` the `isFloating()` test comes before the load test, so an SSE/x87 load (`ldfp`) is never marked speculative: STT never taints it, NDA never delays it, DoM never makes it L1-only. The diagnostic buckets a hit when (1) the transmitter's backward register slice ends at a direct SSE load (`movq mem,%xmmK`) (`_fv2_slice.py`, the bug agent's `bucket_fp.py` rule), and (2) the GPR-only twin (same stem and mode in `STT_6_fv2`, same build) ran ok and did not hit.

**Evidence.** `wiki/findings/audits/2026-11-08/SOURCE_AUDIT_RECON.md` R-SA-13 'gem5 check': on the first 300 tests, E2 121/121 and E8 50/50 fp-only hits have this producer and 0/177 fv2fp tests without it hit; the E2 fp-only ld hits store-forward, but their GPR twins hold (not A2/R-SA-9).

**Verdict.** Real gem5 defense bug, known. Scope: build-specific, gem5-recon-modded schemes 1 and 2 on a testset with SSE loads (2026-11-09: `E2_STT_6_fv2fp`, `E8_STT_6_fv2fp`). Not installed on E9 (DoM): it matched 0 there, because every E9 fv2fp hit also hits in its GPR twin.

**Second path (2026-11-09).** Some fv2fp tests hit and so do their GPR twins, because the twin hits by A2 store forwarding. For these, the hit is bucketed here only when the faithful rerun (`recon_stlf_evidence.json`) shows the transmitter's own `STL_CHECK` as `isTainted=0 isSpeculative=1` and every producer on its slice is an SSE load. gem5 itself says the address lost its taint, and the only source is the never-speculative `ldfp`. Example: inst-027890 is `isTainted=1` (A2) in fv2, but in fv2fp, through `movq (%r10,%r15),%xmm15; movq %xmm15,%r15`, it is `isTainted=0`. On E2 fv2fp this matched 38 of the 86 ld tests whose twin also hit.

**Third path, NDA (2026-11-09).** On E8 fv2fp, 22 ld tests whose GPR twin also hits (there by R-SA-18 forwarding) have a single SSE-load producer whose own rerun `STL_CHECK` is `isSpeculative=0` (`nda_fwd_evidence.json`). That is R-SA-13 seen directly in gem5, so they are bucketed here.
