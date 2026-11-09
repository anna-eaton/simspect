#!/usr/bin/env python3
"""
diag_dom_xmit_store_forward.py: KNOWN CAUSE, criterion pending (PHASE known_pending). On DoM
(gem5-recon-modded scheme 3, row E9) the transmitter load obtained its data by store-to-load
forwarding (check_ld cache_fate=store_forward, data_obtained=True) in every in-window record of the
test: it made no cache access, which Delay-on-Miss permits by design (DoM delays only L1 misses).
check_ld's data-obtained gate scores store_forward as a leak (specs/leakage/recon.json); whether that
counts on DoM is the open criterion question R-SA-18 / Q6
(wiki/findings/audits/2026-11-08/SOURCE_AUDIT_RECON.md; URGENT_TODO DoM DECIDE).

Signature (pure raw-record, NEEDS_GEM5=False): the campaign's own _sweep_raw records for this
<mode>/<stem> that are in window all have cache_fate == "store_forward" and data_obtained true.
Scope: DoM campaigns only (E9 fv2 and fv2fp). Never on STT/NDA rows: there a forwarded transmitter
still means the defense let its tainted/unsafe address operand through. Bug note:
diag_dom_xmit_store_forward.md.
"""
import json, glob, functools, collections
from pathlib import Path

PHASE = "known_pending"; CATEGORY = "criterion_pending:R-SA-18_dom_store_forward"; NEEDS_GEM5 = False; ORDER = 50
KINDS = ("ld",)
MODE = None
HERE = Path(__file__).resolve().parent


@functools.lru_cache(maxsize=1)
def _raw():
    d = collections.defaultdict(list)
    for f in glob.glob(str(HERE.parent / "mispredict_*" / "_sweep_raw" / "*.json")):
        mode = Path(f).parts[-3]
        for r in json.load(open(f)):
            if r.get("issued_in_window"):
                d[(mode, r["name"].split("__")[0])].append(r)
    return d


def is_known(stem, xml_dir):
    recs = _raw().get((MODE, stem), [])
    if not recs:
        return False, "no in-window raw record"
    if all(r.get("cache_fate") == "store_forward" and r.get("data_obtained") is True for r in recs):
        return True, f"{len(recs)} in-window record(s), all store_forward (no cache access)"
    return False, "some in-window record is not a store forward"
