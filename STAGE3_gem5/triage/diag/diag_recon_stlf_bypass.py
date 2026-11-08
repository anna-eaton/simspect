#!/usr/bin/env python3
"""
diag_recon_stlf_bypass.py — REAL BUG (known, A2): on /work/gem5-recon-modded
scheme 2 (Recon-STT), a load the defense itself marks tainted AND speculative
gets its data by store-to-load forwarding and completes inside the speculation
window.

ONE cause; build-specific (applies to every campaign on gem5-recon-modded, with
that campaign's own evidence file). Same bug as
results/Recon_6__latest/diagnostics/diag_recon_slf.py and
wiki/findings/bug/recon_SLF_stlf_bypass/, re-verified 2026-11-07 under the fixed
harness on an unfiltered trace: right after "Executing load" the LSQ prints
"STL_CHECK: load PC <xmit> isTainted=1 isSpeculative=1", then "Forwarding from
store idx N to load", and Commit marks the load ready within the ROB about 2500
cycles before the window-opening branch resolves.

Signature (all, from recon_stlf_evidence.json, one faithful re-run per mode):
the hit reproduced, STL_CHECK shows isTainted=1 isSpeculative=1 for the xmit,
a "Forwarding from store" line follows its execute, and its ready-within-ROB
tick is before the window-opening branch's resolve_visible tick.
Verdict: real gem5 defense bug (implementation forwards without the STT check).
"""
import json, functools
from pathlib import Path

PHASE = "real_bug"; CATEGORY = "real_bug"; NEEDS_GEM5 = False; ORDER = 10
KINDS = ("ld",)
MODE = None
HERE = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def _ev():
    p = HERE / "recon_stlf_evidence.json"
    return json.loads(p.read_text()) if p.exists() else {}


def is_known(stem, xml_dir):
    r = _ev().get(f"{MODE}/{stem}")
    if r is None:
        return False, "no evidence"
    ok = (r.get("reproduced", True) and "isTainted=1 isSpeculative=1" in r["stl"] and r["fwd"]
          and r["ready_in_window"])
    return (True, f"tainted+speculative load forwarded from a store, ready at {r['ready_tick']} < branch resolve {r['ctrl_visible']}") if ok else (False, "signature incomplete")
