#!/usr/bin/env python3
"""
diag_brx_const_condition.py — DISQUALIFIER: SPT br_x hit whose branch condition is
built only from constants in the compiled program, so SPT never taints it and is
allowed to resolve the branch inside the window.

ONE cause, the br_x twin of diag_constaddr_load. SPT taints only what a load
produces (rob_impl.hh:236-250: a load always taints its destination, any other
instruction taints its destination iff a source is tainted), and the Lazy
implicit-flow rule delays a mispredicted branch's squash only when its arguments
are tainted (commit_impl.hh:944). The Alloy model nevertheless puts the
condition in the protection set (Branchxs.inreg in leakage_function), so it
asks for a leak SPT is not designed to prevent. Verdict: model over-approximation
(protection set counts constant-derived values), not a gem5 bug.

Signature (all three, read from the precomputed evidence file
spt_brx_evidence.json written by STAGE3_gem5/triage/run_spt_brx_triage.sh):
  (1) x86 slice (STAGE3_gem5/triage/spt_cond_slice.py) of the jcc's flags on the
      Alloy-order path reaches no load: verdict "const";
  (2) the hit reproduced in a faithful gem5 re-run at the hit's grid point;
  (3) in that run gem5-spt did NOT make the transmitter branch's first
      mispredicting instance pending (no "(Lazy) A branch ... made pending" line)
      and VPUntaints == 0 (nothing had to be untainted).
Missing evidence -> not matched (stays NEW). Counterfactual proof that the rule
is live: inst-080310 with its constant source replaced by a load of (%rsp) is
made pending and no longer hits (triage/counterfactual/, 2026-11-07).
"""
import json, functools
from pathlib import Path

PHASE = "disqualifier"; CATEGORY = "artifact"; NEEDS_GEM5 = False; ORDER = 40
KINDS = ("br_x",)
MODE = None
HERE = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def _ev():
    p = HERE / "spt_brx_evidence.json"
    return {f"{r['mode']}/{r['stem']}": r for r in json.loads(p.read_text())} if p.exists() else {}


def is_known(stem, xml_dir):
    r = _ev().get(f"{MODE}/{stem}")
    if r is None:
        return False, "no evidence"
    if r["slice"] == "const" and r["reproduced"] and not r["xmit_first_made_pending"] and str(r["VPUntaints"]) == "0":
        return True, f"condition from constants; gem5 did not delay the branch (grid {r['grid']})"
    return False, f"slice={r['slice']} pending={r['xmit_first_made_pending']} VPUntaints={r['VPUntaints']}"
