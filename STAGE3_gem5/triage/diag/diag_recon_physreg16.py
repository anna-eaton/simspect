#!/usr/bin/env python3
"""
diag_recon_physreg16.py — REAL BUG (R-SA-12): on the gem5-recon* builds with the STT taint tracker
(--scheme=2), a value renamed to physical int register 16 is never tainted, because
src/cpu/o3/secure_scheme/taint_tracker.cc:59 `if (regId->flatIndex() == 16) return;` drops the insert.
x86 has no zero register, so phys int 16 is an ordinary renamable register (first mapped to microcode
temp t0, then recycled through the free list).

ONE cause; build-specific scope: every campaign on /work/gem5-recon, /work/gem5-recon-modded,
/work/gem5-recon-stl and /work/gem5-recon-ruby3 at scheme 2 (the tracker is used only under
Scheme::STT, rename.cc:714). Load transmitters only (KINDS = ld): for br_x the tracker's verdict is not
printed, so br_x hits stay NEW.

Evidence: recon_physreg16_evidence.json in this directory, written by
STAGE3_gem5/triage/recon_physreg16_check.py from one faithful re-run per (mode, stem) with the Rename
debug flag. A hit is bucketed only if ALL hold (see that script's docstring):
  S1 the re-run reproduces the hit;
  S2 gem5's own STL_CHECK for the xmit's decisive execution says isTainted=0 isSpeculative=1;
  S3 replaying STT's rename rule over the xmit's register slice WITH the reg-16 skip gives "untainted"
     (agrees with gem5);
  S4 the same replay WITHOUT the skip gives "tainted";
  S5 some instruction in the slice writes IntRegClass phys 16 and would be tainted without the skip;
  S6 allowlistedTaintsFromTT == 0 in the re-run (no ReCon untaint);
  S7 every rename block in the slice parsed cleanly.
Anything else (missing evidence, no reproduction, ambiguous parse) stays NEW.
Verdict: real gem5 defense bug (taint invariant violated by an implementation special case).
Bug write-up: diag_recon_physreg16.md (next to this file).
"""
import json, functools
from pathlib import Path

PHASE = "real_bug"; CATEGORY = "real_bug"; NEEDS_GEM5 = False; ORDER = 20
KINDS = ("ld",)
MODE = None
HERE = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def _ev():
    p = HERE / "recon_physreg16_evidence.json"
    return json.loads(p.read_text()) if p.exists() else {}


def is_known(stem, xml_dir):
    r = _ev().get(f"{MODE}/{stem}")
    if r is None:
        return False, "no evidence"
    if not r.get("signature"):
        miss = [k for k in ("reproduced", "gem5_untainted", "via16", "no_reveal", "parse_ok") if not r.get(k)]
        if r.get("sim_with_rule") is not False:
            miss.append("sim_with_rule!=False")
        if not r.get("sim_without_rule"):
            miss.append("sim_without_rule")
        return False, "signature incomplete: " + ",".join(miss)
    return True, (f"xmit sn {r['xmit_seq']} untainted per STL_CHECK; slice writes phys int 16 at sn {r['via16']} "
                  f"from speculative origin(s) {r['origins']}; tainted without the taint_tracker.cc:59 skip")
