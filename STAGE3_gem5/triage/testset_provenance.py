#!/usr/bin/env python3
"""Which generation is each testset? (2026-11-07)

For every testset dir given, read provenance.tar.gz and print the sha256 of each
archived file (the .als, parsexml.py, configs), plus the xml/asm/ann counts and
mtimes. Compare the hashes against git history with the companion step in
wiki/state/TESTSET_GENERATIONS (see claudelog 2026-11-07).

    python3 testset_provenance.py <testset_dir> [...] --out prov.json
"""
import argparse, hashlib, json, os, tarfile, time
from pathlib import Path


def _count(d):
    try:
        with os.scandir(d) as it:
            n = 0; lo = hi = None
            for e in it:
                n += 1
                if n <= 2000:
                    m = e.stat().st_mtime
                    lo = m if lo is None else min(lo, m); hi = m if hi is None else max(hi, m)
            return n, lo, hi
    except FileNotFoundError:
        return None, None, None


def _ts(x):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(x)) if x else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    out = {}
    for d in a.dirs:
        rec = dict(path=str(d), real=str(d.resolve()), provenance={}, dirs={})
        p = d / "provenance.tar.gz"
        if p.exists():
            rec["provenance_mtime"] = _ts(p.stat().st_mtime)
            with tarfile.open(p) as tf:
                for m in tf.getmembers():
                    if m.isfile():
                        rec["provenance"][m.name] = hashlib.sha256(tf.extractfile(m).read()).hexdigest()
        for sub in ["xml", "llvm", "asm", "ann"] + [f"{m}/{s}" for m in
                    ("mispredict_not_taken", "mispredict_taken", "stl_bypass") for s in ("llvm", "asm", "ann")]:
            n, lo, hi = _count(d / sub)
            if n is not None:
                rec["dirs"][sub] = dict(n=n, mtime_sample_min=_ts(lo), mtime_sample_max=_ts(hi))
        out[str(d)] = rec
        print(d, json.dumps(rec["provenance"]), json.dumps(rec["dirs"]))
    if a.out:
        a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
