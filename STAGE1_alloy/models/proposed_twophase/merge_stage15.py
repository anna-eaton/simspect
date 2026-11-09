#!/usr/bin/env python3
"""merge_stage15.py — merge one family's Stage-1.5 output into a single numbered testset XML dir.

DRAFT TOOLING (2026-11-09, simspect-c8). Input: <ws>/s15/<family>/out/<core>/inst-*.xml
(launch_stage15.py). Output: <dest>/xml/inst-NNNNNN.xml (renumbered, copies), plus
  <dest>/merge_map.jsonl       one row per kept XML: new name, core, source file, fingerprint id
  <dest>/merge_dups.jsonl      one row per dropped XML: source file, the kept XML it duplicates
  <dest>/MERGE_PROVENANCE.json counts, inputs, code sha256s, the dedup rule
  <dest>/merge.log             start/end, progress, every parse error with its traceback

Dedup rule: the fingerprint of STAGE2_compilation/find_duplicates.py:canonicalize (instruction
kinds, resolved/committed flags, slots with canonical state names, ddi and rf edges,
register/memory counts) PLUS each instruction's `xm` flag, which canonicalize leaves out (two
instances that differ only in which instruction is the transmitter must not merge). Cores are
visited in sorted order and XMLs in name order; the first copy of each fingerprint is kept. An XML
that fails to parse is logged and dropped (never silently).

Usage (inside gem5_dev):
  python3 merge_stage15.py --ws /tests/simspect_alloy_20261108 --family STT_6 \
      --code /tests/simspect_alloy_20261108/code_20261109 \
      --dest /tests/simspect_alloy_20261108/testsets_twostage/STT_6 --jobs 48
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import traceback
from multiprocessing import Pool
from pathlib import Path


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


_FNS = None


def _init(code_stage2):
    global _FNS
    sys.path.insert(0, code_stage2)
    from parsexml import parse_alloy_xml, pass1_specify_state_a
    from find_duplicates import canonicalize
    _FNS = (parse_alloy_xml, pass1_specify_state_a, canonicalize)


def fingerprint(path):
    parse_alloy_xml, pass1, canonicalize = _FNS
    try:
        inst = parse_alloy_xml(Path(path).read_text())
        r1 = pass1(inst, write_out=False)
        fp = (canonicalize(r1, inst), tuple(bool(r.get("xm")) for r in r1["instructions"]))
        return path, hashlib.sha256(repr(fp).encode()).hexdigest(), None
    except Exception:
        return path, None, traceback.format_exc()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--family", required=True)
    ap.add_argument("--code", required=True, help="code snapshot root (has STAGE2_compilation/)")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--jobs", type=int, default=32)
    a = ap.parse_args()

    ws, dest = Path(a.ws), Path(a.dest)
    src_root = ws / "s15" / a.family / "out"
    stage2 = str(Path(a.code) / "STAGE2_compilation")
    if (dest / "xml").exists() and any((dest / "xml").iterdir()):
        raise SystemExit(f"refusing: {dest}/xml already populated")
    (dest / "xml").mkdir(parents=True, exist_ok=True)
    log = open(dest / "merge.log", "a", buffering=1)

    def L(msg):
        log.write(f"{now()} {msg}\n")

    files = []
    for core in sorted(p for p in src_root.iterdir() if p.is_dir()):
        files += [str(x) for x in sorted(core.glob("inst-*.xml"))]
    L(f"START family={a.family} host={os.uname().nodename} files={len(files)} jobs={a.jobs} src={src_root}")

    kept, dups, errors = {}, 0, 0
    order = {f: i for i, f in enumerate(files)}
    results = {}
    with Pool(a.jobs, initializer=_init, initargs=(stage2,)) as pool:
        for n, (path, fp, err) in enumerate(pool.imap_unordered(fingerprint, files, chunksize=64), 1):
            results[path] = (fp, err)
            if n % 20000 == 0:
                L(f"progress fingerprinted={n}/{len(files)}")
    mm = open(dest / "merge_map.jsonl", "w")
    md = open(dest / "merge_dups.jsonl", "w")
    for path in sorted(files, key=order.get):
        fp, err = results[path]
        if err:
            errors += 1
            L(f"PARSE_ERROR {path}\n{err}")
            continue
        if fp in kept:
            dups += 1
            md.write(json.dumps({"source": path, "duplicate_of": kept[fp]}) + "\n")
            continue
        name = f"inst-{len(kept) + 1:06d}.xml"
        kept[fp] = name
        shutil.copyfile(path, dest / "xml" / name)
        p = Path(path)
        mm.write(json.dumps({"name": name, "core": p.parent.name, "source": path, "fp": fp[:16]}) + "\n")
    mm.close()
    md.close()
    prov = {"family": a.family, "created": now(), "host": os.uname().nodename,
            "source_dir": str(src_root), "source_xmls": len(files), "kept": len(kept),
            "duplicates_dropped": dups, "parse_errors": errors,
            "dedup_rule": "find_duplicates.canonicalize + per-instruction xm flag; first copy kept (cores sorted, files by name)",
            "code": {f: sha(Path(a.code) / f) for f in
                     ("STAGE2_compilation/parsexml.py", "STAGE2_compilation/find_duplicates.py")},
            "stage15_provenance": str(ws / "s15" / a.family / "PROVENANCE.json")}
    (dest / "MERGE_PROVENANCE.json").write_text(json.dumps(prov, indent=1))
    L(f"END kept={len(kept)} duplicates={dups} parse_errors={errors}")
    print(json.dumps(prov, indent=1))


if __name__ == "__main__":
    main()
