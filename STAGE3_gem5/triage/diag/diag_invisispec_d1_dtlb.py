#!/usr/bin/env python3
"""
diag_invisispec_d1_dtlb.py: KNOWN DEVIATION D-1: the only offending events are DTLB replacement
touches by speculative (non-store) hits (`tlb.cc` updates lruSeq on every hit; the paper delays
D-TLB replacement updates to the visibility point, §VI-E3), plus, on Futuristic only, store-actor
artifacts. Known and acknowledged (invisispec_flagged_events_triage.md §1; SOURCE_AUDIT_INVISISPEC.md
"Known and not counted"; AMULET_BUGS_DETECTION_ACCOUNTING.md §4 "bucketed separately (D-1)").

Signature (diagnostics/invisispec_evidence.json, faithful rerun): at least one `d1` event and every
offending event is `d1` (or `store` on Futuristic). Scope: every InvisiSpec campaign (E12a, E12b).
PHASE real_bug (a real implementation deviation, already known). Bug note: diag_invisispec_d1_dtlb.md.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _fv2_evidence as E  # noqa: E402

PHASE = "real_bug"; CATEGORY = "known_deviation:D-1_dtlb_lru_touch"; NEEDS_GEM5 = False; ORDER = 30
KINDS = ("ld", "br_x")
MODE = None


def is_known(stem, xml_dir):
    r = E.evidence("invisispec").get(f"{MODE}/{stem}")
    if not E.usable(r):
        return False, "no usable rerun evidence"
    ok = {"d1", "store"}
    cls = [E.invisispec_class(e) for e in r.get("offending_events") or []]
    if "d1" in cls and all(c in ok for c in cls):
        return True, f"{cls.count('d1')} DTLB repl_touch by speculative hits" + (" + store-actor events" if "store" in cls else "")
    return False, "not DTLB-touch-only"
