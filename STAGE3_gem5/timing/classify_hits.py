#!/usr/bin/env python3
"""classify_hits.py: attribute each hit of a timing_driver.py campaign to known
bug signatures, then compute time-to-first-detection (timing-amulet, 2026-11-09).

    python3 classify_hits.py <timing_out_dir> --defense invisispec|cleanupspec|speclfb|stt \
        [--stage3 /tests/simspect_alloy_20261108/code_20261109/STAGE3_gem5]

Signatures (every one reuses an existing, documented rule; a hit can carry several):
  InvisiSpec  UV1        some in-window offending event (the checker's `offending` event ids) is
                         `L1D:evict` with req=specld (AMULET_BUGS_DETECTION_ACCOUNTING.md §2 UV1 row).
              other_<struct>  hit whose offending items include no such event (listed by struct).
  CleanupSpec UV4 / UV5 / CS1 / EM_upgrade / unattributed: the per-item causes of
                         STAGE3_gem5/triage/cleanupspec_skip_evidence.py (run unchanged on a shim
                         campaign layout); UV3 is not reachable here (no RMW transmitter in the testset).
  SpecLFB     UV6 (rank-0 speculative load, `uv6_first`), walk_order, jmp_shadow: the per-event tags of
                         speclfb_analyze.py (vendored helpers/analyze.py) after triage.py's disqualifier
                         (in-window events whose req is not ld are dropped).
  STT         none (no shared detection target; hits only counted).

Writes <out>/classes.jsonl (one row per hit: idx, mode, stem, sigs) and <out>/first_detection.json:
per signature, the first idx (0-based order position) whose test carries it, tests-to-first =
idx+1 among tests attempted in order, cumulative gem5 CPU s and total harness CPU s over idx 0..first,
K (tests with the signature) of N (tests finished in the contiguous prefix), and the rate-based
expectation (N+1)/(K+1). Log: <out>/classify.log.
"""
import argparse, collections, gzip, json, os, shutil, subprocess, sys, tempfile, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGETS = {"invisispec": ["UV1"], "cleanupspec": ["UV4", "UV3", "UV5"],
           "speclfb": ["UV6", "walk_order", "jmp_shadow"], "stt": []}


def load_rows(out: Path):
    rows = {}
    for l in (out / "results.jsonl").read_text().splitlines():
        try:
            r = json.loads(l)
            rows[r["idx"]] = r
        except Exception:
            pass
    return rows


def gunzip_tmp(gz: Path) -> Path:
    fd, p = tempfile.mkstemp(suffix=".pipeview.txt")
    with gzip.open(gz, "rb") as fi, os.fdopen(fd, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    return Path(p)


def sigs_invisispec(raw, pv, gc):
    evs = {e["id"]: e for e in gc.parse_simspect_events(pv)}
    sigs, structs = set(), set()
    for o in raw.get("offending") or []:
        structs.add(o.get("struct"))
        for i in o.get("event_ids") or []:
            e = evs.get(i)
            if e and e["struct"] == "L1D" and e["kind"] == "evict" and e.get("req") == "specld":
                sigs.add("UV1")
    if not sigs:
        sigs |= {f"other_{s}" for s in sorted(structs, key=str)}
    return sigs


def sigs_speclfb(raw, pv, mode, an):
    a = an.analyze(raw, str(pv), mode)
    good = [c for c in a.get("causes") or [] if c["ev"].get("req") in ("ld",)]
    tags = {c["tag"] for c in good}
    sigs = set()
    if "uv6_first" in tags:
        sigs.add("UV6")
    if "walk_order" in tags or any("walk_order" in t for t in tags):
        sigs.add("walk_order")
    if any(t.startswith("jmp_shadow") for t in tags):
        sigs.add("jmp_shadow")
    if not sigs:
        sigs.add("other:" + ("+".join(sorted(tags)) if tags else "disq_non_load_footprint"))
    return sigs


def cleanupspec_all(out: Path, hits, log):
    shim = out / "cs_evidence"
    shutil.rmtree(shim, ignore_errors=True)
    for r in hits:
        rawf = out / "raw" / r["mode"] / f"{r['stem']}.json"
        if not rawf.exists():
            continue
        d = shim / r["mode"] / "_sweep_raw"
        d.mkdir(parents=True, exist_ok=True)
        rec = json.loads(rawf.read_text())
        rec.pop("workdir", None)
        (d / f"{r['stem']}.json").write_text(json.dumps([rec]))
        td = shim / "diagnostics" / "traces" / r["mode"]
        td.mkdir(parents=True, exist_ok=True)
        gz = out / "traces" / r["mode"] / f"{r['stem']}.pipeview.txt.gz"
        if gz.exists():
            (td / gz.name).symlink_to(gz)
    p = subprocess.run([sys.executable, str(HERE / "cleanupspec_skip_evidence.py"), str(shim)],
                       capture_output=True, text=True)
    log.write(f"cleanupspec_skip_evidence rc={p.returncode}\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}\n")
    ev = json.loads((shim / "diagnostics" / "cleanupspec_skip_evidence.json").read_text())
    name = {"UV4_split": "UV4", "UV5_older_load": "UV5", "CS1_older_store_upgrade": "CS1",
            "EM_upgrade_squashed": "EM_upgrade", "unattributed": "unattributed"}
    return {k: {name.get(c, c) for c in v.get("causes", [])} for k, v in ev.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--defense", required=True, choices=["invisispec", "cleanupspec", "speclfb", "stt"])
    ap.add_argument("--stage3", default="/tests/simspect_alloy_20261108/code_20261109/STAGE3_gem5")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    os.environ["SIMSPECT_STAGE3"] = args.stage3
    sys.path.insert(0, args.stage3)
    log = open(out / "classify.log", "a")
    log.write(f"== start {time.strftime('%F %T')} defense={args.defense}\n")
    rows = load_rows(out)
    hits = [r for r in rows.values() if r.get("hit")]
    cls = {}
    if args.defense == "cleanupspec":
        try:
            m = cleanupspec_all(out, hits, log)
        except Exception:
            log.write(traceback.format_exc())
            m = {}
        for r in hits:
            cls[r["idx"]] = m.get(f"{r['mode']}/{r['stem']}", {"no_evidence"})
    elif args.defense in ("invisispec", "speclfb"):
        import gem5_common as gc
        an = None
        if args.defense == "speclfb":
            sys.path.insert(0, str(HERE))
            import speclfb_analyze as an
        for r in hits:
            gz = out / "traces" / r["mode"] / f"{r['stem']}.pipeview.txt.gz"
            rawf = out / "raw" / r["mode"] / f"{r['stem']}.json"
            if not gz.exists() or not rawf.exists():
                cls[r["idx"]] = {"no_trace"}
                continue
            pv = gunzip_tmp(gz)
            try:
                raw = json.loads(rawf.read_text())
                cls[r["idx"]] = (sigs_invisispec(raw, pv, gc) if args.defense == "invisispec"
                                 else sigs_speclfb(raw, pv, r["mode"], an))
            except Exception:
                log.write(f"ERROR idx={r['idx']} {r['mode']}/{r['stem']}\n{traceback.format_exc()}\n")
                cls[r["idx"]] = {"classify_error"}
            finally:
                pv.unlink(missing_ok=True)
    else:
        for r in hits:
            cls[r["idx"]] = {"hit(no target)"}
    with open(out / "classes.jsonl", "w") as f:
        for i in sorted(cls):
            f.write(json.dumps(dict(idx=i, mode=rows[i]["mode"], stem=rows[i]["stem"], kind=rows[i].get("kind"),
                                    sigs=sorted(cls[i]))) + "\n")
    # contiguous finished prefix 0..N-1 (parallel workers can leave holes at the tail)
    N = 0
    while N in rows:
        N += 1
    cum_g = cum_t = 0.0
    first = {}
    K = collections.Counter()
    st = collections.Counter()
    for i in range(N):
        r = rows[i]
        cum_g += r.get("gem5_cpu_s") or 0
        cum_t += r.get("total_cpu_s") or 0
        st[r.get("status")] += 1
        for s in cls.get(i, ()):
            K[s] += 1
            if s not in first:
                first[s] = dict(first_idx=i, tests_to_first=i + 1, stem=r["stem"], mode=r["mode"],
                                cum_gem5_cpu_s=round(cum_g, 2), cum_total_cpu_s=round(cum_t, 2))
    res = dict(defense=args.defense, N_prefix=N, n_rows=len(rows), status=dict(st),
               hits=sum(1 for i in range(N) if rows[i].get("hit")),
               gem5_cpu_s_total=round(cum_g, 2), total_cpu_s_total=round(cum_t, 2),
               gem5_cpu_s_per_test=round(cum_g / N, 3) if N else None,
               total_cpu_s_per_test=round(cum_t / N, 3) if N else None,
               signatures={s: dict(first.get(s, {}), K=K[s], N=N, expected_tests_to_first=round((N + 1) / (K[s] + 1), 2),
                                   expected_gem5_cpu_s_to_first=round((N + 1) / (K[s] + 1) * cum_g / N, 2) if N else None,
                                   expected_total_cpu_s_to_first=round((N + 1) / (K[s] + 1) * cum_t / N, 2) if N else None)
                           for s in sorted(set(K) | set(TARGETS[args.defense]))})
    (out / "first_detection.json").write_text(json.dumps(res, indent=1))
    log.write(json.dumps(res) + f"\n== end {time.strftime('%F %T')}\n")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
