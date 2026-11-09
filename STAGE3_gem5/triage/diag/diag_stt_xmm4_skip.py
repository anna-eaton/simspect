#!/usr/bin/env python3
"""
diag_stt_xmm4_skip.py: REAL BUG S1 (STT taint dropped through xmm4, FP register index 16).

ONE cause; build-specific: STT trees that carry the `srcRegIdx(i).index() == 16` source skip
(/work/stt rob_impl.hh:229, /work/stt-master rob_impl.hh:229, /work/amulet/amulet-gem5-STT_AE-v1.1
rob_impl.hh:230). Install only in campaigns on those builds (rows E3, E4) whose testset routes values
through xmm registers (STT_6_fv2fp). Write-up: wiki/findings/bug/stt_xmm4_taint_skip/README.md;
bucket note: diag_stt_xmm4_skip.md next to this file.

Signature (static, NEEDS_GEM5=False), all must hold:
  * the transmitter's backward register slice (ld: address registers; br_x: compare source) reads
    or writes %xmm4 (_fv2_slice.transmitter_slice, the bug agent's bucket_fp.py rule);
  * the GPR-only twin (same stem + mode in STT_6_fv2 on the same build) ran ok and did NOT hit
    (diagnostics/twin_fv2/<mode>/<kind>/window-results.json). So the xmm routing is the only
    difference, and the bug agent's controlled rerun (xmm4 -> xmm3 rename kills 3/3 hits on E3 and E4)
    shows xmm4 is what matters.
Verdict: real gem5 defense bug (STT implementation), known, found by our pipeline.
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _fv2_slice as S  # noqa: E402

PHASE = "real_bug"; CATEGORY = "real_bug:S1_stt_xmm4_taint_skip"; NEEDS_GEM5 = False; ORDER = 20
KINDS = ("ld", "br_x")
MODE = None


def is_known(stem, xml_dir):
    md = S.mode_dir_of(xml_dir, MODE)
    kind = S.kind_of(stem, md)
    if kind not in KINDS:
        return False, "kind not handled"
    t = S.twin_held(stem, MODE, kind)
    if t is not True:
        return False, "GPR twin hit or unknown"
    sl = S.transmitter_slice(stem, md)
    if sl.get("err"):
        return False, sl["err"]
    if not sl["xmm4"]:
        return False, "no xmm4 on the transmitter slice"
    return True, "xmm4 on the transmitter slice (" + "; ".join(sl["slice"])[:200] + "); GPR twin held"
