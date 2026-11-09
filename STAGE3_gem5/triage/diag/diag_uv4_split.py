#!/usr/bin/env python3
"""
diag_uv4_split.py: REAL BUG (known, AMuLeT UV4) on CleanupSpec
(amulet-gem5-CleanupSpec_AE-v1.1): a squashed cache-line-crossing (split) load is
never cleaned (`L1D:cleanup_skip why=split`; lsq_unit_impl.hh:2529-2535
"TODO: Cleanup For SplitReq"), so its L1D/L2 installs and its L1D victim stay.

ONE cause. Scope: every footprint campaign on the CleanupSpec build. Bug note:
diag_uv4_split.md next to this file. The cache-setup classifier labelled these
records "UV4_split_plus_other"; the "other" item is the victim the same split
load evicted, so the whole record is UV4.

Signature (from diagnostics/cleanupspec_skip_evidence.json, built by
STAGE3_gem5/triage/cleanupspec_skip_evidence.py): every offending item of every
hitting variant has cause UV4_split, i.e. the item's event is a fill (L1D or L2)
or an L1D evict by an actor S that never committed, and the trace has
`L1D:cleanup_skip seq=S why=split` (for fills, on the same line). Anything else
stays NEW.
"""
import functools
import json
from pathlib import Path

PHASE = "real_bug"; CATEGORY = "UV4"; NEEDS_GEM5 = False; ORDER = 21
KINDS = ("ld",)
MODE = None
CAUSE = "UV4_split"
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
    lines = sorted({f"{i['struct']}:{i['line']}" for v in r["variants"] for i in v["items"]})
    return True, f"split load never cleaned, cleanup_skip why=split ({', '.join(lines)})"
