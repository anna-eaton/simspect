#!/usr/bin/env python3
"""
diag_brx_declassified_condition.py — DISQUALIFIER: SPT br_x hit whose branch
condition is a load value that a NON-speculative load/store of the compiled
program also uses as its address, so SPT legitimately untaints it before the
branch resolves.

ONE cause. In SPT a memory transmitter that reaches the visibility point
untaints its tainted address registers (lsq_unit_impl.hh:1185-1207, 1262-1279;
cpu.cc:2132), and forward propagation then cleans the copies that feed the
branch (rob_impl.hh:800). The value has been leaked non-speculatively, which SPT
does not protect by design. In the Alloy instance that co-transmitter is not
rf-linked to the same source (diag_nonspec_cotransmit / diag_store_cotransmit
do not match): concretization gave both operands the same register (shared
Reg_s state without an rf edge). Verdict: concretization/model artifact (the
program has a data dependency the instance does not), not a gem5 bug. Open
question for Anna: whether shared opstate without rf should be allowed at all
(see wiki/results/results.md 2026-11-07).

Signature (all, from spt_brx_evidence.json): x86 slice verdict "declassified"
(lists the declassifying instruction), the hit reproduced, gem5 did not make the
transmitter branch's first mispredicting instance pending, and VPUntaints >= 1.
Counterfactual proof: inst-043417 with the store's address register changed from
%rax to %r12 has VPUntaints 0, every transmitter-branch instance is made pending,
and the hit disappears (triage/counterfactual/, 2026-11-07).
"""
import json, functools
from pathlib import Path

PHASE = "disqualifier"; CATEGORY = "artifact"; NEEDS_GEM5 = False; ORDER = 45
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
    if (r["slice"] == "declassified" and r["reproduced"] and not r["xmit_first_made_pending"]
            and str(r["VPUntaints"]) not in ("0", "None")):
        return True, f"declassified by {r['declassified_by']}; gem5 did not delay the branch (grid {r['grid']})"
    return False, f"slice={r['slice']} pending={r['xmit_first_made_pending']} VPUntaints={r['VPUntaints']}"
