#!/usr/bin/env python3
"""
rerun_hits_evidence.py: faithful batched rerun of a testrun.py campaign's hits with traces kept only
for the length of one batch, feeding one evidence analyzer (bucket-fv2, 2026-11-09).

Why: the fanout-v2 campaigns ran with keep_tmp=false, so trace-based diagnostics (recon STLF bypass,
CleanupSpec skip causes, SpecLFB UV6 tags, InvisiSpec UV1 req) need a rerun. Disk stays bounded:
each batch's gem5 workdirs live in <work>/tmp/<batch> (TMPDIR) and are deleted right after the batch
is analyzed (only the analyzer's small JSON, and for `cs_trace` one gzipped pipeview per hit, stay).

Faithful: the campaign's own config (manifest.json "config"), verbatim except paths.* (stage dir /
results dir under <work>), pipeline.keep_tmp=true, gem5.jobs, gem5.sample_fraction removed (explicit
stem list), speculation.branch_modes=[<mode>], and optional extra debug flags (--extra-debug, print
only). Same pipeline.py gem5 path as the campaign, so the same grid, per-branch random stalls and
cache_setup. Each analyzer checks reproduction (the rerun's own hit verdict and/or the campaign
record's offending event ids reappearing with the same struct+line).

Analyzers (one per run):
  recon_stlf   ld hits on gem5-recon-modded: per xmit execution, the LSQ STL_CHECK line, a
               "Forwarding from store" line, Commit "ready within ROB" (needs --extra-debug Commit),
               and the held branch's resolve_visible. Output keyed "<mode>/<stem>" in the format of
               recon_stlf_check.py, read unchanged by diag/diag_recon_stlf_bypass.py.
  cs_trace     CleanupSpec: gzip each hit's pipeview into <shim>/diagnostics/traces/<mode>/<stem>.pipeview.txt.gz
               and its campaign raw records into <shim>/<mode>/_sweep_raw/, for cleanupspec_skip_evidence.py <shim>.
  speclfb      SpecLFB: classify_hits.sigs_speclfb (speclfb_analyze tags: UV6 / walk_order / jmp_shadow / other:*).
  invisispec   InvisiSpec: classify_hits.sigs_invisispec (UV1 = an offending L1D evict with req=specld)
               plus the req of every offending L1D evict event (to validate raw-record rules).

Usage (in the gem5_dev container):
  python3 rerun_hits_evidence.py --campaign <results/X__latest> --testset-src <testsets_twostage/STT_6_fv2>
      --code <code root> --work <bugwork dir> --analyzer recon_stlf --out <evidence.json>
      [--kinds ld] [--keys-file f] [--batch 16] [--jobs 8] [--extra-debug Commit] [--shim DIR]
Log: <work>/logs/rerun_<analyzer>_<campaign>.log (start/end, per batch, every error with traceback).
Resumable: keys already in --out are skipped.
"""
import argparse, collections, gzip, json, os, random, re, shutil, subprocess, sys, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_jsonc(p):
    return json.loads("\n".join(l for l in Path(p).read_text().splitlines() if not l.lstrip().startswith("//")))


def campaign_hits(camp, kinds):
    out = {}
    for wr in sorted(Path(camp).glob("mispredict_*/*/window-results.json")):
        mode, kind = wr.parts[-3], wr.parts[-2]
        if kinds and kind not in kinds:
            continue
        for r in json.loads(wr.read_text()):
            if r.get("issued_in_window"):
                out[(mode, r["name"].split("__")[0])] = kind
    return out


def campaign_raw(camp, wanted):
    raw = collections.defaultdict(list)
    for f in sorted(Path(camp).glob("mispredict_*/_sweep_raw/*.json")):
        mode = f.parts[-3]
        m = re.search(r"grid(\d+)", f.name)
        for r in json.loads(f.read_text()):
            k = (mode, r["name"].split("__")[0])
            if k in wanted:
                r = dict(r); r["_grid"] = int(m.group(1)) if m else None; r["_rawfile"] = f.name
                raw[k].append(r)
    return raw


def _trace(wd):
    return Path(wd) / "m5out" / "pipeview.txt"


def _offending_repro(rec, evs):
    """Determinism check: the rerun trace has the campaign record's n_simspect_events, and every
    offending event id reappears with the same struct (and the same seq when the record lists seqs).
    (The checker's offending `line` is derived differently from the event's `line` field, so it is
    not compared.)"""
    n = rec.get("n_simspect_events")
    if n is not None and n != len(evs):
        return False
    for o in rec.get("offending") or []:
        seqs = set(o.get("seqs") or [])
        for i in o.get("event_ids") or []:
            e = evs.get(i)
            if not e or e.get("struct") != o.get("struct"):
                return False
            if seqs and e.get("seq") not in seqs:
                return False
    return True


# ── analyzers ────────────────────────────────────────────────────────────────

def an_recon_stlf(stem, mode, wds, raws, rerun_hit, A):
    import gem5_common as gc
    xpc = next((r.get("xmit_pc") for r in raws if r.get("xmit_pc")), None)
    out = dict(stem=stem, mode=mode, reproduced=bool(rerun_hit), stl="", fwd=False, ready_tick=None,
               ctrl_visible=None, ready_in_window=False, n_workdirs=len(wds), xmit_pc=xpc)
    if not xpc:
        out["error"] = "no xmit_pc in campaign records"; return out
    x = xpc[2:]
    for wd in wds:
        tr = _trace(wd)
        if not tr.exists():
            continue
        L = tr.read_text(errors="replace").splitlines()
        idx = [k for k, l in enumerate(L) if "Executing load PC (0x" + x in l]
        br = gc.parse_branch_events(tr)
        ctrl = [d for s in br.values() for d in s.values() if d.get("resolve_hold")]
        cv = min((d["resolve_visible"] for d in ctrl if d.get("resolve_visible")), default=None)
        for k in idx:
            sn = re.search(r"sn:(\d+)", L[k]).group(1)
            win = L[k:k + 6]
            stl = next((l.split(": ", 2)[-1] for l in win if "STL_CHECK" in l), "")
            fwd = any("Forwarding from store" in l for l in win)
            rdy = next((int(l.split(":")[0]) for l in L[k:] if f"[sn:{sn}] ready within ROB" in l), None)
            riw = bool(rdy and cv and rdy < cv)
            better = (fwd and rdy and "isTainted=1 isSpeculative=1" in stl and riw)
            if not out["stl"] or better:
                out.update(stl=stl, fwd=fwd, ready_tick=rdy, ctrl_visible=cv, ready_in_window=riw,
                           xmit_seq=int(sn), workdir_name=Path(wd).name)
            if better:
                return out
    return out


def _uops(tr):
    """seq -> micro-op text from the O3PipeView fetch lines (`...:fetch:<tick>:<pc>:<upc>:<seq>: MNEM : uop args`)."""
    out = {}
    with open(tr, errors="replace") as f:
        for ln in f:
            if ln.startswith("O3PipeView:fetch:"):
                p = ln.rstrip("\n").split(":", 6)
                if len(p) == 7:
                    try:
                        out[int(p[5])] = p[6].strip()
                    except ValueError:
                        pass
    return out


def _sig(rec):
    return sorted({(o.get("struct"), tuple(sorted(o.get("kinds") or [o.get("term")]))) for o in rec.get("offending") or []})


def an_cs_trace(stem, mode, wds, raws, rerun_hit, A, rr=None):
    """Gzip the rerun's trace + write the RERUN's own records into the shim (so event ids match the
    trace even when the Ruby rerun is not bit-identical to the campaign run). Only stems whose rerun
    hit with the campaign's offending (struct, kinds) signature are written; others get no evidence."""
    shim = Path(A.shim)
    if len(wds) != 1:
        return dict(error=f"{len(wds)} workdirs (expected 1)")
    tr = _trace(wds[0])
    hit = [r for r in raws if r.get("issued_in_window")]
    rrh = [r for r in (rr or []) if r.get("issued_in_window")]
    if not tr.exists() or not hit:
        return dict(error="no trace or no campaign hit record")
    same = bool(rrh) and _sig(rrh[0]) == _sig(hit[0])
    out = dict(reproduced=bool(rrh), same_signature=same)
    if not same:
        return out
    td = shim / "diagnostics" / "traces" / mode; td.mkdir(parents=True, exist_ok=True)
    gz = td / f"{stem}.pipeview.txt.gz"
    with tr.open("rb") as fi, gzip.open(gz, "wb", compresslevel=6) as fo:
        shutil.copyfileobj(fi, fo)
    rd = shim / mode / "_sweep_raw"; rd.mkdir(parents=True, exist_ok=True)
    recs = [{k: v for k, v in r.items() if k != "workdir"} for r in rr]
    (rd / f"{stem}.json").write_text(json.dumps(recs))
    out["trace"] = str(gz)
    return out


def an_footprint_sigs(defense):
    """Classify the RERUN's own hit record against the rerun's own trace (self-consistent even when the
    rerun is not bit-identical to the campaign run, as happens on the Ruby InvisiSpec build). Records:
    reproduced (rerun hit), same_signature (rerun offending (struct, kinds) set == campaign's),
    bit_identical (campaign offending ids reappear, same n_simspect_events)."""
    def f(stem, mode, wds, raws, rerun_hit, A, rr=None):
        import gem5_common as gc
        import classify_hits as ch
        if len(wds) != 1:
            return dict(error=f"{len(wds)} workdirs (expected 1)")
        tr = _trace(wds[0])
        hit = [r for r in raws if r.get("issued_in_window")]
        rrh = [r for r in (rr or []) if r.get("issued_in_window")]
        if not tr.exists() or not hit:
            return dict(error="no trace or no campaign hit record")
        evs = {e["id"]: e for e in gc.parse_simspect_events(tr)}
        out = dict(reproduced=bool(rrh), bit_identical=_offending_repro(hit[0], evs),
                   same_signature=bool(rrh) and _sig(rrh[0]) == _sig(hit[0]))
        if not rrh:
            return out
        raw = rrh[0]
        if defense == "speclfb":
            import speclfb_analyze as an
            a = an.analyze(raw, str(tr), mode)
            out["tags"] = sorted({f"{c['tag']}|req={c['ev'].get('req')}" for c in a.get("causes") or []})
            out["sigs"] = sorted(ch.sigs_speclfb(raw, tr, mode, an))
        else:
            out["sigs"] = sorted(ch.sigs_invisispec(raw, tr, gc))
        ev_req = collections.Counter()
        uop = _uops(tr) if defense == "invisispec" else {}
        detail = []
        for o in raw.get("offending") or []:
            for i in o.get("event_ids") or []:
                e = evs.get(i)
                if e:
                    ev_req[f"{e['struct']}:{e['kind']}:req={e.get('req')}"] += 1
                    if defense == "invisispec":
                        detail.append(dict(id=i, struct=e["struct"], kind=e["kind"], req=e.get("req"), seq=e.get("seq"),
                                           uop=uop.get(e.get("seq"))))
                else:
                    detail.append(dict(id=i, missing=True))
        out["offending_event_reqs"] = dict(ev_req)
        if defense == "invisispec":
            out["offending_events"] = detail
        return out
    return f


def an_dump(stem, mode, wds, raws, rerun_hit, A):
    """debug: keep each workdir's pipeview gzipped under <work>/dump/<mode>/."""
    out = []
    for wd in wds:
        tr = _trace(wd)
        if tr.exists():
            d = Path(A.work) / "dump" / mode; d.mkdir(parents=True, exist_ok=True)
            gz = d / f"{Path(wd).name}.pipeview.txt.gz"
            with tr.open("rb") as fi, gzip.open(gz, "wb") as fo:
                shutil.copyfileobj(fi, fo)
            out.append(str(gz))
    return dict(reproduced=bool(rerun_hit), dumps=out)


def an_nda_fwd(stem, mode, wds, raws, rerun_hit, A):
    """NDA (R-SA-18 NDA half): is the transmitter's address producer P (static slice producer load,
    diag/_fv2_slice.py) store-forwarded while speculative? Per workdir: every execution of a load whose
    PC lies in P's litmus block [label(P), label(P+1)), its STL_CHECK line and a following
    "Forwarding from store" line; and the transmitter's first "Executing load" tick."""
    import gem5_common as gc
    sys.path.insert(0, str(HERE / "diag")); sys.path.insert(0, str(Path(A.work) / "diag"))
    import _fv2_slice as S
    sl = S.transmitter_slice(stem, str(Path(A.testset_src) / mode))
    xpc = next((r.get("xmit_pc") for r in raws if r.get("xmit_pc")), None)
    out = dict(reproduced=bool(rerun_hit), producers=sl.get("producers"), slice=sl.get("slice"), err=sl.get("err"),
               xmit_pc=xpc, runs=[])
    prods = [p for p in (sl.get("producers") or [])]
    if len(prods) != 1 or not xpc:
        out["error"] = f"{len(prods)} producers (need exactly 1) or no xmit_pc"; return out
    ppc = prods[0]["pc"]
    xaddr = int(xpc, 16)
    for wd in wds:
        tr = _trace(wd); b = Path(wd) / stem
        if not tr.exists() or not b.exists():
            continue
        lab = gc._litmus_labels(b, stem)
        lo, hi = lab.get(ppc), lab.get(ppc + 1)
        if lo is None or hi is None:
            continue
        L = tr.read_text(errors="replace").splitlines()
        pex, xt = [], None
        for k, l in enumerate(L):
            m = re.search(r"Executing load PC \(0x([0-9a-f]+)=>", l)
            if not m:
                continue
            a = int(m.group(1), 16)
            if lo <= a < hi:
                win = L[k:k + 6]
                pex.append(dict(tick=int(l.split(":")[0]), pc=hex(a),
                                stl=next((w.split(": ", 2)[-1] for w in win if "STL_CHECK" in w), ""),
                                fwd=any("Forwarding from store" in w for w in win)))
            if a == xaddr and xt is None:
                xt = int(l.split(":")[0])
        out["runs"].append(dict(workdir=Path(wd).name, producer_execs=pex, xmit_first_exec=xt))
    return out


ANALYZERS = {"nda_fwd": an_nda_fwd, "dump": an_dump, "recon_stlf": an_recon_stlf, "cs_trace": an_cs_trace,
             "speclfb": an_footprint_sigs("speclfb"), "invisispec": an_footprint_sigs("invisispec")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", required=True); ap.add_argument("--testset-src", required=True)
    ap.add_argument("--code", required=True); ap.add_argument("--work", required=True)
    ap.add_argument("--analyzer", required=True, choices=sorted(ANALYZERS)); ap.add_argument("--out", required=True)
    ap.add_argument("--kinds", nargs="*"); ap.add_argument("--keys-file")
    ap.add_argument("--sample", type=int, help="random sample of N hit keys (seed 20261109)")
    ap.add_argument("--batch", type=int, default=16); ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--extra-debug", nargs="*", default=[]); ap.add_argument("--shim")
    ap.add_argument("--timeout", type=int, default=7200)
    A = ap.parse_args()
    camp = Path(A.campaign).resolve(); work = Path(A.work).resolve(); code = Path(A.code).resolve()
    sys.path.insert(0, str(code / "STAGE3_gem5")); sys.path.insert(0, str(code)); sys.path.insert(0, str(HERE))
    os.environ["SIMSPECT_STAGE3"] = str(code / "STAGE3_gem5")
    (work / "logs").mkdir(parents=True, exist_ok=True)
    logp = work / "logs" / f"rerun_{A.analyzer}_{camp.name}.log"
    log = open(logp, "a")

    def L(m):
        log.write(f"{time.strftime('%F %T')} {m}\n"); log.flush(); print(m, flush=True)
    L(f"== start campaign={camp} analyzer={A.analyzer} argv={sys.argv[1:]}")
    try:
        man = json.loads((camp / "manifest.json").read_text())
        base_cfg = load_jsonc(man["config"])
        hits = campaign_hits(camp, set(A.kinds or []))
        keys = sorted(hits)
        if A.keys_file:
            want = {tuple(l.strip().split("/", 1)) for l in open(A.keys_file) if l.strip()}
            keys = [k for k in keys if k in want]
        if A.sample and len(keys) > A.sample:
            keys = sorted(random.Random(20261109).sample(keys, A.sample))
        outp = Path(A.out)
        res = json.loads(outp.read_text()) if outp.exists() else {}
        keys = [k for k in keys if f"{k[0]}/{k[1]}" not in res]
        raw = campaign_raw(camp, set(keys))
        L(f"{len(keys)} hit keys to rerun ({len(res)} already done)")
        model = Path(A.testset_src).name
        by_mode = collections.defaultdict(list)
        for m, s in keys:
            by_mode[m].append(s)
        for mode, stems in sorted(by_mode.items()):
            for bi in range(0, len(stems), A.batch):
                chunk = stems[bi:bi + A.batch]
                b = f"{camp.name}_{mode}_{bi // A.batch:04d}"
                stage = work / "stage" / b; tmp = work / "tmp" / b; resd = work / "res" / b
                for d in (stage, tmp, resd):
                    shutil.rmtree(d, ignore_errors=True)
                for sub in ("asm", "ann"):
                    (stage / model / mode / sub).mkdir(parents=True, exist_ok=True)
                for s in chunk:
                    os.symlink(Path(A.testset_src) / mode / "asm" / f"{s}.s", stage / model / mode / "asm" / f"{s}.s")
                    os.symlink(Path(A.testset_src) / mode / "ann" / f"{s}.ann.json", stage / model / mode / "ann" / f"{s}.ann.json")
                tmp.mkdir(parents=True); resd.mkdir(parents=True)
                cfg = json.loads(json.dumps(base_cfg))
                cfg["paths"]["testset_dir"] = str(stage); cfg["paths"]["results_dir"] = str(resd)
                cfg["paths"]["results_name"] = "rr"
                cfg.setdefault("pipeline", {})["keep_tmp"] = True
                cfg["gem5"]["jobs"] = A.jobs; cfg["gem5"].pop("sample_fraction", None)
                cfg["speculation"]["branch_modes"] = [mode]
                if A.extra_debug:
                    cfg["gem5"]["debug_flags"] = list(cfg["gem5"].get("debug_flags", ["O3PipeView"])) + \
                        [f for f in A.extra_debug if f not in cfg["gem5"].get("debug_flags", [])]
                cfgp = stage / "cfg.json"; cfgp.write_text(json.dumps(cfg, indent=1))
                env = dict(os.environ, TMPDIR=str(tmp))
                t0 = time.time()
                with open(work / "logs" / f"{b}.pipeline.log", "w") as plog:
                    p = subprocess.run([sys.executable, "-u", "pipeline.py", "gem5", "--model", model, "--config", str(cfgp),
                                        "--force"], cwd=str(code), env=env, stdout=plog, stderr=subprocess.STDOUT,
                                       timeout=A.timeout)
                L(f"batch {b}: {len(chunk)} stems, pipeline rc={p.returncode}, {time.time() - t0:.0f}s")
                wr = resd / "rr" / mode / "window-results.json"
                rh = {}
                if wr.exists():
                    for r in json.loads(wr.read_text()):
                        rh[r["name"].split("__")[0]] = rh.get(r["name"].split("__")[0], False) or bool(r.get("issued_in_window"))
                else:
                    L(f"  ! no rerun window-results at {wr}")
                wds = collections.defaultdict(list)
                for d in tmp.glob("gem5_inst-*"):
                    m = re.match(r"gem5_(inst-\d+)_", d.name)
                    if m:
                        wds[m.group(1)].append(d)
                rr = collections.defaultdict(list)
                for rf in (resd / "rr" / mode / "sweep" / "raw_results").glob("*.json"):
                    try:
                        for r in json.loads(rf.read_text()):
                            rr[r["name"].split("__")[0]].append(r)
                    except Exception:
                        L(f"  ! unreadable rerun raw {rf}: {traceback.format_exc()}")
                for s in chunk:
                    try:
                        fn = ANALYZERS[A.analyzer]
                        args_ = (s, mode, sorted(wds.get(s, [])), raw.get((mode, s), []), rh.get(s), A)
                        r = fn(*args_, rr=rr.get(s, [])) if A.analyzer in ("speclfb", "invisispec", "cs_trace") else fn(*args_)
                    except Exception:
                        r = dict(error="analyzer exception", tb=traceback.format_exc()[-2000:])
                        L(f"  ERROR {mode}/{s}\n{traceback.format_exc()}")
                    res[f"{mode}/{s}"] = r
                outp.write_text(json.dumps(res, indent=1))
                for d in (stage, tmp, resd):
                    shutil.rmtree(d, ignore_errors=True)
        L(f"== end ok: {len(res)} keys in {outp}")
    except Exception:
        L("== end FAILED\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
