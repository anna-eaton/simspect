#!/usr/bin/env python3
"""
diag_recon_sse_load_producer.py: REAL BUG R-SA-13 (Recon-group builds: FP/SSE loads are never
marked speculative; decode.cc:684-695 tests isFloating() before isLoad()).

ONE cause; build-specific: gem5-recon-modded (and gem5-recon) schemes 1 (NDA) and 2 (STT), rows E8
and E2, on a testset with direct SSE loads (STT_6_fv2fp). Not installed on E9 (DoM): there every fv2fp
hit also hits in the GPR twin, so the SSE load is not what makes it hit. Write-up:
wiki/findings/audits/2026-11-08/SOURCE_AUDIT_RECON.md R-SA-13 'gem5 check'; bucket note
diag_recon_sse_load_producer.md next to this file.

Signature (static, NEEDS_GEM5=False), all must hold:
  * the transmitter's backward register slice ends at a direct SSE load (`movq mem,%xmmK` = ldfp)
    (_fv2_slice.transmitter_slice, the bug agent's bucket_fp.py rule);
  * the GPR-only twin (same stem + mode in STT_6_fv2, same build) ran ok and did NOT hit
    (diagnostics/twin_fv2/<mode>/<kind>/window-results.json).
  OR, when the GPR twin also hit (it hits there by A2 store forwarding), the faithful rerun evidence
    (recon_stlf_evidence.json, rerun_hits_evidence.py --analyzer recon_stlf) shows the transmitter's
    own STL_CHECK as `isTainted=0 isSpeculative=1` and EVERY producer on the slice is an SSE load: gem5
    itself says the address lost its taint, and the only source is the never-speculative ldfp.
  OR (NDA) the same with nda_fwd_evidence.json showing the SSE producer's own STL_CHECK isSpeculative=0.
Bug agent's population check (first 300 tests): E2 121/121 and E8 50/50 fp-only hits have this
producer, 0/177 fv2fp tests without it hit. Verdict: real gem5 defense bug, known.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _fv2_slice as S  # noqa: E402

PHASE = "real_bug"; CATEGORY = "real_bug:R-SA-13_sse_load_not_speculative"; NEEDS_GEM5 = False; ORDER = 15
KINDS = ("ld", "br_x")
MODE = None


def is_known(stem, xml_dir):
    md = S.mode_dir_of(xml_dir, MODE)
    kind = S.kind_of(stem, md)
    if kind not in KINDS:
        return False, "kind not handled"
    sl = S.transmitter_slice(stem, md)
    if sl.get("err"):
        return False, sl["err"]
    sse = [p for p in sl["producers"] if p["sse"]]
    if not sse:
        return False, "no SSE-load producer on the transmitter slice"
    desc = "SSE-load producer " + "; ".join(f"pc{p['pc']} {p['asm']}" for p in sse)
    t = S.twin_held(stem, MODE, kind)
    if t is True:
        return True, desc + "; GPR twin held"
    ev = _stlf().get(f"{MODE}/{stem}")
    if (t is False and ev and ev.get("reproduced") and "isTainted=0 isSpeculative=1" in (ev.get("stl") or "")
            and all(p["sse"] for p in sl["producers"])):
        return True, desc + "; GPR twin hit (A2), but here gem5 STL_CHECK says the transmitter is untainted"
    nf = _nda().get(f"{MODE}/{stem}")
    if (t is False and nf and nf.get("reproduced") and not nf.get("error") and all(p["sse"] for p in sl["producers"])
            and any("isSpeculative=0" in p["stl"] for r in nf.get("runs") or [] for p in r["producer_execs"])):
        return True, desc + "; GPR twin hit, but here gem5 STL_CHECK says the SSE producer is not speculative"
    return False, "GPR twin hit/unknown and no untainted/non-speculative STL_CHECK evidence"


import json, functools  # noqa: E402


@functools.lru_cache(maxsize=1)
def _stlf():
    p = HERE / "recon_stlf_evidence.json"
    return json.loads(p.read_text()) if p.exists() else {}


@functools.lru_cache(maxsize=1)
def _nda():
    p = HERE / "nda_fwd_evidence.json"
    return json.loads(p.read_text()) if p.exists() else {}
