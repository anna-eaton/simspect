#!/usr/bin/env python3
"""
diag_invisispec_store_actor.py: DISQUALIFIER (checker artifact). On InvisiSpec Futuristic, every
offending event of the hit belongs to a store micro-op (req=st, or the seq's micro-op is st/stis/...):
the Futuristic actor does not filter for loads, and a store's write after commit is normal
(wiki/findings/audits/2026-10-28/invisispec_flagged_events_triage.md §2, rows "DTLB:fill/repl_touch
early in inv_fut" and "DIR:coh (+L1D:fill, L2:fill) ... seq 532": CHECKER ARTIFACT).

Scope: InvisiSpec Futuristic campaigns only (row E12a). Evidence: diagnostics/invisispec_evidence.json
(rerun_hits_evidence.py --analyzer invisispec; the faithful rerun must hit with the campaign's
offending signature). Bug note: diag_invisispec_store_actor.md. Verdict: checker artifact, not a leak.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _fv2_evidence as E  # noqa: E402

PHASE = "disqualifier"; CATEGORY = "checker_artifact:futuristic_store_actor"; NEEDS_GEM5 = False; ORDER = 5
KINDS = ("ld", "br_x")
MODE = None


def is_known(stem, xml_dir):
    r = E.evidence("invisispec").get(f"{MODE}/{stem}")
    if not E.usable(r):
        return False, "no usable rerun evidence"
    ev = r.get("offending_events") or []
    cls = [E.invisispec_class(e) for e in ev]
    if ev and all(c == "store" for c in cls):
        return True, f"all {len(ev)} offending events are store micro-ops (Futuristic actor)"
    return False, "not store-only"
