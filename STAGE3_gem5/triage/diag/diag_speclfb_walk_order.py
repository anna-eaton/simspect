#!/usr/bin/env python3
"""
diag_speclfb_walk_order.py: KNOWN CAUSE, verdict pending (PHASE known_pending): SpecLFB walk-order
(the ROB sees a load one cycle before the LQ and the sticky PrevNoUnsafe is never cleared, so a rank>=1
speculative load is marked safe). Whether it is UV6 with a wider scope or a separate bug is Anna's
DECIDE (AMULET_BUGS_DETECTION_ACCOUNTING.md §2 walk-order row). bucket_hits.py ranks unknown phases
after real_bug, so these never land in NEW.

Signature (diagnostics/speclfb_evidence.json, faithful rerun): every req=ld tag is walk_order (and
there is one). Scope: every SpecLFB campaign (E14). Bug note: diag_speclfb_walk_order.md.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _speclfb_common as C  # noqa: E402

PHASE = "known_pending"; CATEGORY = "known_pending:speclfb_walk_order"; NEEDS_GEM5 = False; ORDER = 40
KINDS = ("ld", "br_x")
MODE = None


def is_known(stem, xml_dir):
    r = C.rec(MODE, stem)
    if r is None:
        return False, "no usable rerun evidence"
    t = C.ld_tags(r)
    if t == {"walk_order"}:
        return True, "walk_order only"
    return False, "not walk-order-only"
