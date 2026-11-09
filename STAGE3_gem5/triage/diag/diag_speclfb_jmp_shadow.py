#!/usr/bin/env python3
"""
diag_speclfb_jmp_shadow.py: REAL BUG (found by SimSpect, verified): a direct JMP/CALL inside the
shadow resets prevBrsResolved (rob.cc ROB::updateSafeState), so younger speculative loads are treated
as safe and fill (wiki/findings/bug/speclfb_jmp_shadow/README.md).

Signature (diagnostics/speclfb_evidence.json, faithful rerun): a req=ld `jmp_shadow` or
`jmp_shadow+walk_order` tag, no `uv6_first`, and every req=ld tag in {jmp_shadow, jmp_shadow+walk_order,
walk_order}. Scope: every SpecLFB campaign (E14). Bug note: diag_speclfb_jmp_shadow.md.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _speclfb_common as C  # noqa: E402

PHASE = "real_bug"; CATEGORY = "real_bug:speclfb_jmp_shadow"; NEEDS_GEM5 = False; ORDER = 20
KINDS = ("ld", "br_x")
MODE = None
KNOWN = {"walk_order", "jmp_shadow", "jmp_shadow+walk_order"}


def is_known(stem, xml_dir):
    r = C.rec(MODE, stem)
    if r is None:
        return False, "no usable rerun evidence"
    t = C.ld_tags(r)
    if t & {"jmp_shadow", "jmp_shadow+walk_order"} and t <= KNOWN:
        return True, ",".join(sorted(t))
    return False, "no jmp_shadow or other load tags"
