#!/usr/bin/env python3
"""
diag_invisispec_uv1.py: REAL BUG (known, AMuLeT UV1): a speculative load evicts an L1D line
(`L1D:evict req=specld`, plus the `L2:coh` PUTX writeback); gone with --apply-spec-eviction-patch
(wiki/findings/mdsToRead/AMULET_BUGS_DETECTION_ACCOUNTING.md §2; INVISISPEC_UV1_CONFIRMED.md).

Signature (from diagnostics/invisispec_evidence.json, the faithful rerun's own hit record + trace):
at least one offending event is `uv1`, and EVERY offending event is `uv1`, `wb`, `d1` (known D-1
DTLB LRU touch) or, on Futuristic only, `store` (known checker artifact). Any other event (e.g. an
L1D fill by a speculative load, or an event whose seq has no fetch record) leaves the hit NEW.
Scope: build-specific, every InvisiSpec campaign (rows E12a, E12b). Bug note: diag_invisispec_uv1.md.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _fv2_evidence as E  # noqa: E402

PHASE = "real_bug"; CATEGORY = "real_bug:UV1_invisispec_spec_eviction"; NEEDS_GEM5 = False; ORDER = 10
KINDS = ("ld", "br_x")
MODE = None


def is_known(stem, xml_dir):
    r = E.evidence("invisispec").get(f"{MODE}/{stem}")
    if not E.usable(r):
        return False, "no usable rerun evidence"
    ok = {"uv1", "wb", "d1", "store"}
    cls = [E.invisispec_class(e) for e in r.get("offending_events") or []]
    if "uv1" in cls and all(c in ok for c in cls):
        return True, f"{cls.count('uv1')} L1D evict req=specld; others: " + ",".join(sorted(set(cls) - {'uv1'}))
    return False, "no UV1 eviction or unexplained events"
