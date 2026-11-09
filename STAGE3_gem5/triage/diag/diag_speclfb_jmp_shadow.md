# diag_speclfb_jmp_shadow: SpecLFB jmp-shadow (real gem5 bug, found by SimSpect)

**Issue and signature.** A direct JMP/CALL inside the shadow resets `prevBrsResolved` (`rob.cc` `ROB::updateSafeState`), so younger speculative loads are treated as safe and fill. The diagnostic buckets a hit with a req=ld `jmp_shadow` or `jmp_shadow+walk_order` tag, no `uv6_first`, and every req=ld tag in {jmp_shadow, jmp_shadow+walk_order, walk_order}.

**Evidence.** `wiki/findings/bug/speclfb_jmp_shadow/README.md`; AMULET_BUGS_DETECTION_ACCOUNTING.md §3. Evidence file `speclfb_evidence.json`.

**Verdict.** Real gem5 defense bug (verified). Scope: every SpecLFB campaign (E14).
