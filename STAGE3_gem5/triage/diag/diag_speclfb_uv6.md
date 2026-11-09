# diag_speclfb_uv6: UV6, SpecLFB treats the first speculative load as safe (real gem5 bug, known, AMuLeT)

**Issue and signature.** The first speculative load of a window (rank 0, `LSQ:unsafe unsafe=0 ... lqhead=1`) is not held and fills L1D/L2. The diagnostic buckets a hit when the faithful rerun's req=ld cause tags include `uv6_first` and every req=ld tag is a known SpecLFB cause (`uv6_first`, `walk_order`, `jmp_shadow`, `jmp_shadow+walk_order`). Co-firing tags are named in the reason. Tags like `safe_other`, `unsafe1_filled`, `replayed_after_safe*` or `no_unsafe_line` leave the hit NEW.

**Evidence.** AMULET_BUGS_DETECTION_ACCOUNTING.md §2 UV6 row (1143/1142 of 1500 tests per mode). Evidence file `speclfb_evidence.json`.

**Verdict.** Real gem5 defense bug, known (AMuLeT UV6). Scope: every SpecLFB campaign (E14).
