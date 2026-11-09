#!/usr/bin/env python3
"""
diag_speclfb_nonload_footprint.py: DISQUALIFIER (out of SpecLFB's scope / checker artifact): none of
the hit's in-window footprint events was made by a load (`req` is never `ld`: stores, ifetch,
writebacks). SpecLFB protects speculative loads only (L1D+L2 presence of load fills, §1 p632, §7 p640;
AMULET_BUGS_DETECTION_ACCOUNTING.md scope list), and the 2026-11-07 SpecLFB triage dropped
non-load events the same way (helpers/triage.py; classify_hits.py `disq_non_load_footprint`).

Signature: diagnostics/speclfb_evidence.json, usable rerun, and the set of req=ld cause tags is empty
while at least one tag exists. Scope: every SpecLFB campaign (row E14). Bug note:
diag_speclfb_nonload_footprint.md. Verdict: not a leak SpecLFB promises to stop.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _speclfb_common as C  # noqa: E402

PHASE = "disqualifier"; CATEGORY = "out_of_scope:speclfb_non_load_footprint"; NEEDS_GEM5 = False; ORDER = 5
KINDS = ("ld", "br_x")
MODE = None


def is_known(stem, xml_dir):
    r = C.rec(MODE, stem)
    if r is None:
        return False, "no usable rerun evidence"
    if r.get("tags") and not C.ld_tags(r):
        return True, "no in-window footprint event by a load: " + ",".join(sorted(r["tags"]))[:200]
    return False, "has load footprint"
