#!/usr/bin/env python3
"""
diag_cs1_store_upgrade.py: KNOWN CAUSE, VERDICT PENDING (CS-1) on CleanupSpec
(amulet-gem5-CleanupSpec_AE-v1.1, Cleanup_FOR_L1L2): an OLDER, COMMITTED store
upgrades a squashed load's E install to M, CleanupSpec skips that load's whole
cleanup (`Inv_CLEANUP st=M`, MESI_Two_Level-L1cache.sm:2701-2705), and the line
the load evicted (its victim) is never restored. check_footprint's ownership rule
moves the install to the store but keeps the victim charged to the load, so the
record is a victim-only under_clean.

ONE cause. Scope: every footprint campaign on the CleanupSpec build (a build
behaviour, not a testset artifact). Bug note: diag_cs1_store_upgrade.md next to
this file; write-up SOURCE_AUDIT_CLEANUPSPEC_SPECLFB.md CS-1 + round 3.
PHASE is "known_pending": the hit is understood, but whether it counts as a leak
is Anna's open DECIDE (URGENT_TODO "CS-1 un-charge the victim"); bucket_hits.py
ranks it after real_bug, so it is never mixed with NEW.

Signature (from diagnostics/cleanupspec_skip_evidence.json, built from the
campaign's own traces by STAGE3_gem5/triage/cleanupspec_skip_evidence.py): every
offending item of every hitting variant has cause CS1_older_store_upgrade, i.e.
victim item; actor S never committed; S filled L and evicted V; exactly one
`L1D:hit line=L st=E nst=M req=st` by U between the fill and the skip, U older
than the squashing branch and committed; `L1D:cleanup_skip line=L seq=S
ev=Inv_CLEANUP st=M`; no cleanup_restore of V. Anything else stays NEW.
"""
import functools
import json
from pathlib import Path

PHASE = "known_pending"; CATEGORY = "CS-1"; NEEDS_GEM5 = False; ORDER = 30
KINDS = ("ld",)
MODE = None
CAUSE = "CS1_older_store_upgrade"
HERE = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def _ev():
    p = HERE / "cleanupspec_skip_evidence.json"
    return json.loads(p.read_text()) if p.exists() else {}


def is_known(stem, xml_dir):
    r = _ev().get(f"{MODE}/{stem}")
    if r is None:
        return False, "no evidence"
    if r.get("causes") != [CAUSE]:
        return False, f"causes {r.get('causes')}"
    i = r["variants"][0]["items"][0]
    return True, f"older committed store E->M, cleanup skipped at M, victim {i['line']} never restored ({i['why']})"
