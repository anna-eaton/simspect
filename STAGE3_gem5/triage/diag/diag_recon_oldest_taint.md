# diag_recon_oldest_taint: R-SA-8, Recon-STT keeps only the oldest source's taint (real gem5 bug, known)

**Issue and signature.** When a transmitter's address merges two tainted loads, gem5-recon's taint tracker keeps only the oldest source (`taint_tracker.cc:111-131`). When that older load commits (`freeTaints`, `:138`), the transmitter is released from the delay unit, even though the younger source is still under the held branch. The diagnostic buckets an ld hit when the test is a fanout_v2 OTB test whose OTB transmitter is the test's transmitter (`fanout_v2.otb.applied`, `otb.xmit_pc == xmit.pc`), and the faithful rerun evidence (`recon_stlf_evidence.json`) reproduced the hit with the transmitter's STL_CHECK `isTainted=1 isSpeculative=1`.

**Evidence.** bug-investigate-e2new (claudelog 2026-11-09 18:50): all 11 NEW ld stems per mode of E2 fv2 2% are OTB-transmitter tests, 0 non-OTB. In a traced rerun of inst-086032, the transmitter is released at the tick the older L2 load commits (2976000), while the younger source is under held sn:589. bug-investigate-nostlf confirms 7 more on the no-STLF variant. SOURCE_AUDIT_RECON.md R-SA-8 'gem5 check'.

**Verdict.** Real gem5 defense bug, already known (R-SA-8), reached here through the fanout_v2 OTB splice. Scope: gem5-recon-modded scheme 2 campaigns (E2 fv2, E2 fv2fp).
