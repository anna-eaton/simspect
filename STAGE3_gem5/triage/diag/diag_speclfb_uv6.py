#!/usr/bin/env python3
"""
diag_speclfb_uv6.py: REAL BUG (known, AMuLeT UV6): the first speculative load of the window
(rank 0, `LSQ:unsafe unsafe=0 ... lqhead=1`) is treated as safe and fills L1D/L2.

Signature (diagnostics/speclfb_evidence.json, faithful rerun, speclfb_analyze.py tags of req=ld
events): `uv6_first` present, and every req=ld tag is one of the known SpecLFB causes uv6_first,
walk_order, jmp_shadow, jmp_shadow+walk_order. Any other load tag (safe_other, unsafe1_filled,
replayed_after_safe*, no_unsafe_line) leaves the hit NEW. Co-firing walk-order / jmp-shadow events
are named in the reason. Scope: every SpecLFB campaign (E14). Bug note: diag_speclfb_uv6.md.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _speclfb_common as C  # noqa: E402

PHASE = "real_bug"; CATEGORY = "real_bug:UV6_speclfb_first_load"; NEEDS_GEM5 = False; ORDER = 10
KINDS = ("ld", "br_x")
MODE = None
KNOWN = {"uv6_first", "walk_order", "jmp_shadow", "jmp_shadow+walk_order"}


def is_known(stem, xml_dir):
    r = C.rec(MODE, stem)
    if r is None:
        return False, "no usable rerun evidence"
    t = C.ld_tags(r)
    if "uv6_first" in t and t <= KNOWN:
        return True, "uv6_first" + (" (+" + ",".join(sorted(t - {"uv6_first"})) + ")" if t - {"uv6_first"} else "")
    return False, "no uv6_first or unknown load tags"
