#!/usr/bin/env python3
"""
diag_recon_oldest_taint.py: REAL BUG (known, R-SA-8, getOldestTaint) on gem5-recon-modded scheme 2.
A transmitter whose address merges two tainted loads keeps only the OLDEST source's taint
(taint_tracker.cc:111-131); when that older load commits (freeTaints, :138) the transmitter is released
from the delay unit although the younger source is still under the held branch.

Signature (static ann + rerun evidence, NEEDS_GEM5=False): the test is a fanout_v2 OTB test whose OTB
transmitter IS the test's transmitter (ann fanout_v2.otb.applied and otb.xmit_pc == xmit.pc), and the
faithful rerun (recon_stlf_evidence.json) reproduced the hit with the transmitter's STL_CHECK
`isTainted=1 isSpeculative=1` (gem5 taints it, so this is not a lost-taint case).
Evidence: bug-investigate-e2new (claudelog 2026-11-09 18:50): 11/11 E2 fv2 NEW stems per mode are
OTB-xmit tests, 0 non-OTB; traced rerun of inst-086032 shows `Released tainted load` at the older L2's
commit. SOURCE_AUDIT_RECON.md R-SA-8 'gem5 check'. Scope: gem5-recon-modded scheme 2 (E2).
Bug note: diag_recon_oldest_taint.md.
"""
import json, functools, os
from pathlib import Path

PHASE = "real_bug"; CATEGORY = "real_bug:R-SA-8_oldest_taint"; NEEDS_GEM5 = False; ORDER = 12
KINDS = ("ld",)
MODE = None
HERE = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def _ev():
    p = HERE / "recon_stlf_evidence.json"
    return json.loads(p.read_text()) if p.exists() else {}


def is_known(stem, xml_dir):
    md = Path(os.path.abspath(str(xml_dir))).parent / MODE
    try:
        ann = json.loads((md / "ann" / f"{stem}.ann.json").read_text())
    except OSError:
        return False, "no ann"
    otb = (ann.get("fanout_v2") or {}).get("otb") or {}
    if not (otb.get("applied") and otb.get("xmit_pc") == ann.get("xmit", {}).get("pc")):
        return False, "not an OTB-transmitter test"
    r = _ev().get(f"{MODE}/{stem}")
    if not r or not r.get("reproduced") or "isTainted=1 isSpeculative=1" not in (r.get("stl") or ""):
        return False, "no rerun evidence of a tainted transmitter"
    return True, f"OTB transmitter (merge of pc{otb.get('l2_before_pc')} and pc{otb.get('producer_pc')}), gem5-tainted, executes in window"
