#!/usr/bin/env python3
"""
_fv2_evidence.py: shared reader for the rerun evidence files written by
STAGE3_gem5/triage/rerun_hits_evidence.py (bucket-fv2, 2026-11-09). Not a diagnostic.

evidence(name) -> {"<mode>/<stem>": record} from diagnostics/<name>_evidence.json.
usable(rec) -> the faithful rerun hit AND its offending (struct, kinds) signature equals the
campaign record's (rerun_hits_evidence `same_signature`). Records that fail this are never bucketed.

InvisiSpec event classes (used by the diag_invisispec_* diagnostics), per offending event of the
rerun's own hit record, with `uop` = that seq's micro-op from the O3PipeView fetch line:
  uv1        L1D evict with req=specld (AMuLeT UV1; AMULET_BUGS_DETECTION_ACCOUNTING.md §2)
  wb         L2 coh with req=wb (the PUTX writeback of an L1D eviction; part of the UV1 signature)
  d1         DTLB repl_touch (by a non-store seq, or a seq with no fetch record) (D-1: DTLB LRU touch on a speculative hit,
             invisispec_flagged_events_triage.md §1, SOURCE_AUDIT_INVISISPEC.md "known and not counted")
  store      the event's req is st, or its seq's micro-op is a store (st/stis/stfp/stul...): the
             Futuristic actor does not filter for loads (invisispec_flagged_events_triage.md §2,
             CHECKER ARTIFACT). 2026-11-09: also seen on the Spectre scheme (E12b), same mechanism: a
             store micro-op with no pipeview record gets an infinite visibility point, and its normal
             post-commit write is counted (triage §2, seq 532 case).
  other      anything else (includes events whose seq has no fetch record)
"""
import json, functools, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_STORE_UOP = re.compile(r"^\s*\S+\s*:\s*st[a-z0-9]*\b")


@functools.lru_cache(maxsize=None)
def evidence(name):
    p = HERE / f"{name}_evidence.json"
    return json.loads(p.read_text()) if p.exists() else {}


def usable(rec):
    return bool(rec) and not rec.get("error") and rec.get("reproduced") and rec.get("same_signature")


def is_store_uop(uop):
    return bool(uop) and bool(_STORE_UOP.match(uop))


def invisispec_class(e):
    if e.get("missing"):
        return "other"
    st, kd, rq = e.get("struct"), e.get("kind"), e.get("req")
    if rq == "st" or is_store_uop(e.get("uop")):
        return "store"
    if st == "L1D" and kd == "evict" and rq == "specld":
        return "uv1"
    if st == "L2" and kd == "coh" and rq == "wb":
        return "wb"
    if st == "DTLB" and kd == "repl_touch":
        return "d1"   # replacement-state touch on a DTLB hit; same D-1 deviation whatever the micro-op
                      # (seqs with no fetch record are non-first micro-ops of a macro-op)
    return "other"


@functools.lru_cache(maxsize=1)
def futuristic():
    """True when this campaign's InvisiSpec scheme is Futuristic (from ../manifest.json extra args)."""
    try:
        m = json.loads((HERE.parent / "manifest.json").read_text())
        return any("Futuristic" in a for a in m.get("gem5_extra_args") or [])
    except (OSError, ValueError):
        return False
