#!/usr/bin/env python3
"""
summarize_runs.py: per-campaign status / error / hit counts, split by the cache_setup each
test actually ran with (2026-11-09, cache-random session).

Reads the full checker records of testrun.py campaigns (<campaign>/<mode>/_sweep_raw/*.json;
every record carries `cache_setup`, and under gem5.cache_setup random also
`cache_setup_mode`/`cache_setup_seed`). For each campaign prints: records, ok/error/invalid,
the distinct error messages (first 90 chars), hits, and the same split by cache_setup.
With --ref <campaign>, also the hit stems gained/lost against that campaign (same stems only).

Usage: python3 summarize_runs.py [--ref <campaign>] [--json <out>] <campaign> [<campaign> ...]
"""
import argparse
import collections
import glob
import json
import os
import sys


def load(camp):
    recs = []
    for f in sorted(glob.glob(os.path.join(camp, "mispredict_*", "_sweep_raw", "*.json"))):
        mode = f.split(os.sep)[-3]
        for r in json.load(open(f)):
            r["_mode"] = mode
            recs.append(r)
    return recs


def summarize(camp):
    recs = load(camp)
    st = collections.Counter(r.get("status") for r in recs)
    errs = collections.Counter((r.get("error") or "")[:90] for r in recs if r.get("status") == "error")
    hits = {(r["_mode"], r["name"].split("__")[0]) for r in recs if r.get("issued_in_window") is True}
    by = collections.defaultdict(lambda: collections.Counter())
    for r in recs:
        c = r.get("cache_setup", "?")
        by[c]["records"] += 1
        by[c][r.get("status")] += 1
        by[c]["hits"] += r.get("issued_in_window") is True
    return dict(campaign=camp, records=len(recs), status=dict(st), errors=dict(errs.most_common()),
                hits=len(hits), hit_stems=sorted("/".join(h) for h in hits),
                stems=sorted({f"{r['_mode']}/{r['name'].split('__')[0]}" for r in recs}),
                by_cache_setup={k: dict(v) for k, v in by.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaigns", nargs="+")
    ap.add_argument("--ref")
    ap.add_argument("--json")
    a = ap.parse_args()
    ref = summarize(a.ref) if a.ref else None
    out = []
    for c in a.campaigns:
        s = summarize(c)
        print(f"== {c}\n   records {s['records']}  status {s['status']}  hits {s['hits']}")
        for e, n in s["errors"].items():
            print(f"   err x{n}: {e}")
        for k, v in sorted(s["by_cache_setup"].items()):
            print(f"   cache_setup={k}: {v}")
        if ref:
            common = set(s["stems"]) & set(ref["stems"])
            h, rh = set(s["hit_stems"]) & common, set(ref["hit_stems"]) & common
            s["vs_ref"] = dict(ref=a.ref, common=len(common), hits=len(h), ref_hits=len(rh),
                               gained=sorted(h - rh), lost=sorted(rh - h))
            print(f"   vs ref ({len(common)} common stems): hits {len(h)} vs {len(rh)}; "
                  f"gained {sorted(h - rh)}; lost {sorted(rh - h)}")
        out.append(s)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=2)


if __name__ == "__main__":
    sys.exit(main())
