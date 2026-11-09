#!/usr/bin/env python3
"""
diag_uv3_rmw.py: REAL BUG (known, AMuLeT UV3): on CleanupSpec
(amulet-gem5-CleanupSpec_AE-v1.1, Cleanup_FOR_L1L2), a squashed RMW transmitter
installs its line with a write request and CleanupSpec skips the undo.

ONE cause. Scope: CleanupSpec footprint campaigns on the RMW corpus
(testsets_latest/STT_6_rmw, made by STAGE2_compilation/make_rmw_corpus.py); it
matches nothing on a corpus without RMWs. Mechanism: the RMW's `ldst` micro-op
becomes RMW_Read/GETX in Ruby; Sequencer::writeCallback sets only L1Hit, so the
LSQ's cleanup finds no L2Hit/L2Miss and logs `cleanup_skip why=nohitinfo`
(wiki/design/VOCAB_TABLES.md "RMW agent findings (2026-11-08)", CleanupSpec row;
AMuLeT §4.6 p11). Bug note: diag_uv3_rmw.md next to this file (results dir).

Signature (all, from diagnostics/uv3_rmw_evidence.json, built from the campaign's
own kept traces by STAGE3_gem5/triage/uv3_rmw_evidence.py): for every hitting
variant of the stem, terms_fired is exactly under_clean and every offending
(struct, line) event is an L1D fill req=st msg=ST or an L2 fill req=st msg=GETX at
the xmit pc, by an instance that never retired, followed by
`L1D:cleanup_skip line=<same line> seq=<same seq> why=nohitinfo`. Anything else,
including a missing evidence entry, stays NEW.

Cache setup (2026-11-09, cache-random): the textbook chain needs the RMW line to be
absent at the start (gem5.cache_setup cold, or random's cold half). Every evidence
variant must carry the record's own `cache_setup` (the strategy that test actually
ran with; under `random` it differs per test); a variant without it (evidence built
by the pre-2026-11-09 uv3_rmw_evidence.py) is not bucketed. The xmit pc the
evidence compares against is the record's own (re-resolved under cold), never the
original annotation. The reason string names the cache_setup, and bucket_hits.py
splits its summary by it.
"""
import functools
import json
from pathlib import Path

PHASE = "real_bug"; CATEGORY = "UV3"; NEEDS_GEM5 = False; ORDER = 20
KINDS = ("ld",)
MODE = None
HERE = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def _ev():
    p = HERE / "uv3_rmw_evidence.json"
    return json.loads(p.read_text()) if p.exists() else {}


def is_known(stem, xml_dir):
    r = _ev().get(f"{MODE}/{stem}")
    if r is None:
        return False, "no evidence"
    vs = r.get("variants", [])
    if any("cache_setup" not in v for v in vs):
        return False, "evidence lacks the per-record cache_setup (rebuild with uv3_rmw_evidence.py)"
    if not r.get("uv3"):
        return False, "; ".join(v.get("why", "") for v in vs if not v.get("uv3"))
    d = [x for v in vs for x in v.get("details", [])]
    lines = sorted({f"{x['struct']}:{x['line']}" for x in d})
    cs = "+".join(sorted({v["cache_setup"] for v in vs}))
    return True, (f"cache_setup={cs}: RMW write-request fill at the xmit, cleanup_skip why=nohitinfo "
                  f"({', '.join(lines)}; seq {d[0]['seq']})")
