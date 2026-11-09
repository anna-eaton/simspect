#!/usr/bin/env python3
"""_speclfb_common.py: shared tag reader for the diag_speclfb_* diagnostics (bucket-fv2). Not a diagnostic.
Reads diagnostics/speclfb_evidence.json (rerun_hits_evidence.py --analyzer speclfb): per hit, the
speclfb_analyze.py cause tags of the faithful rerun's in-window footprint events as "<tag>|req=<req>".
ld_tags(rec) = the tags of events with req=ld (triage.py's rule: in-window events whose req is not ld
are dropped), or None when the record is not usable."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _fv2_evidence as E  # noqa: E402


def rec(mode, stem):
    r = E.evidence("speclfb").get(f"{mode}/{stem}")
    return r if E.usable(r) else None


def ld_tags(r):
    return {t.split("|req=")[0] for t in r.get("tags") or [] if t.endswith("|req=ld")}


def all_tags(r):
    return {t.split("|req=")[0] for t in r.get("tags") or []}
