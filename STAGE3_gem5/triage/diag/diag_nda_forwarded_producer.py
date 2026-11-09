#!/usr/bin/env python3
"""
diag_nda_forwarded_producer.py: KNOWN CAUSE R-SA-18 (NDA half), leak status pending (PHASE known_pending).
On NDA (gem5-recon-modded scheme 1), the transmitter's address producer P is a speculative load that got
its data by store-to-load forwarding. The forward's WritebackEvent calls writeback() directly and skips
NDA's delay (lsq_unit.cc:2008-2012, :77-86 vs the delay in completeDataAccess :194-210), so P's value
wakes the transmitter at once. Real NDA implementation defect; whether it is a security leak (the
forwarded value is register data from an older in-flight store) is Q6 / R-SA-18
(wiki/findings/audits/2026-11-08/SOURCE_AUDIT_RECON.md R-SA-18 'gem5 check', bug-investigate-ndastl).

Signature (diagnostics/nda_fwd_evidence.json, rerun_hits_evidence.py --analyzer nda_fwd, faithful rerun):
the rerun reproduced the hit; the transmitter's static slice has exactly one producer load P
(_fv2_slice.py); in some rerun run, an execution of P has STL_CHECK `isSpeculative=1` followed by
`Forwarding from store`, and the transmitter's first execution is at or after it.
Scope: NDA campaigns (row E8). Bug note: diag_nda_forwarded_producer.md.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _fv2_evidence as E  # noqa: E402

PHASE = "known_pending"; CATEGORY = "known_pending:R-SA-18_nda_forward_bypass"; NEEDS_GEM5 = False; ORDER = 30
KINDS = ("ld",)
MODE = None


def is_known(stem, xml_dir):
    r = E.evidence("nda_fwd").get(f"{MODE}/{stem}")
    if not r or r.get("error") or not r.get("reproduced"):
        return False, "no usable rerun evidence"
    for run in r.get("runs") or []:
        x = run.get("xmit_first_exec")
        for p in run.get("producer_execs") or []:
            if "isSpeculative=1" in p["stl"] and p["fwd"] and x is not None and x >= p["tick"]:
                return True, f"producer {p['pc']} speculative and store-forwarded at {p['tick']}; xmit executes at {x}"
    return False, "producer not a speculative forwarded load"
