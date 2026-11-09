#!/usr/bin/env python3
"""
diag_cleanupspec_em.py: REAL BUG (UV3 family, E->M path; not an AMuLeT-listed
signature) on CleanupSpec (amulet-gem5-CleanupSpec_AE-v1.1, Cleanup_FOR_L1L2).

A squashed load S installs line L in E. The squashed RMW transmitter U (`orq $0,(mem)`,
its `ldst` micro-op, Ruby RMW_Read with secondary type ST) hits L and upgrades it E->M
(`transition({E,M}, Store, M)`, MESI_Two_Level-L1cache.sm:2294-2298; no speculation
check on the mandatory-queue path, :855-905). U's own cleanup skips (`why=l1hit`: it
installed nothing). S's cleanup then meets L in M and `transition(M, Inv_CLEANUP)`
(:2701-2705) skips the L1 invalidate, the L2 invalidate and the victim rollback, a skip
the paper intends only for an OLDER NON-SQUASHED store (§3.4 p7). L (and S's victim,
if any) stay. Root assumption broken: "RFOs are issued non-speculatively" (p8 §4), the
same one UV3 breaks; AMuLeT's UV3 patch (writeCallback hit metadata) does not reach this
path (U is an L1 hit; the skip is in S's cleanup).

ONE cause. Scope: CleanupSpec footprint campaigns on a corpus whose transmitter is a
memory RMW (STT_6_rmw); matches nothing without RMWs. Bug note: diag_cleanupspec_em.md.

Signature (from diagnostics/cleanupspec_em_evidence.json, written by
STAGE3_gem5/triage/cleanupspec_em_evidence.py from the campaign's own kept traces):
every offending item of every hitting variant has cause EM_rmw_squashed, i.e.
under_clean on L (fill, L1D or L2) or on S's victim V (evict); S and U never committed,
both younger than the squashing branch, S != U; exactly one `L1D:hit line=L st=E nst=M
req=st` between S's install and S's cleanup, by U at the record's xmit pc;
`L1D:cleanup_skip seq=U why=l1hit`; exactly one `L1D:cleanup_skip line=L seq=S
ev=Inv_CLEANUP st=M`; for victim items, no cleanup_restore of V. Anything else
(mixed causes, an older committed upgrader = CS-1, a missing trace) stays NEW.
"""
import functools
import json
from pathlib import Path

PHASE = "real_bug"; CATEGORY = "UV3-EM"; NEEDS_GEM5 = False; ORDER = 22
KINDS = ("ld",)
MODE = None
CAUSE = "EM_rmw_squashed"
HERE = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def _ev():
    p = HERE / "cleanupspec_em_evidence.json"
    return json.loads(p.read_text()) if p.exists() else {}


def is_known(stem, xml_dir):
    r = _ev().get(f"{MODE}/{stem}")
    if r is None:
        return False, "no evidence"
    if r.get("causes") != [CAUSE]:
        return False, f"causes {r.get('causes')}"
    i = r["variants"][0]["items"][0]
    return True, f"squashed RMW xmit upgraded a squashed load's E line to M; cleanup skipped at M ({i['why']})"
