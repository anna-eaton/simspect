#!/usr/bin/env python3
"""timing_driver.py: time-to-first-detection runs for the AMuLeT-parity T rows
(timing-amulet, 2026-11-09; wiki/state/EVAL_MANIFEST.md "AMuLeT-parity runs").

Runs the tests of one testset in a FIXED-SEED random order (same order for every
defense), one pipeline.py gem5 call per test, at most --parallel at once, and
records per test: gem5 CPU time (user+sys of the gem5 process, from the
sitecustom/sitecustomize.py os.wait4 hook), gem5 wall, total harness CPU (the
whole pipeline.py subtree: compile + checker + gem5, from os.wait4 on it), wall,
the checker verdict, and (for hits) the raw checker record + the gzipped trace,
so tools/classify can attribute each hit to a bug signature afterwards.

The run config is used verbatim except for per-test plumbing that pipeline.py
needs (staged testset path, tmp results path, one branch mode, jobs=1,
keep_tmp=true so the hit trace can be kept). No gem5 flag, structure, stall or
checker setting is changed.

    python3 timing_driver.py --code-root /tests/simspect_alloy_20261108/code_20261109 \
        --config runconfigs/amulet_parity_fv2/T2_STT_6_fv2.jsonc --model STT_6_fv2 \
        --out /tests/simspect_alloy_20261108/results_fv2/T2_STT_6_fv2__timing \
        --seed 20261109 --n 600 --parallel 2

Outputs in --out: order.tsv (idx, mode, stem; written once), results.jsonl (one
row per finished test, appended), raw/<mode>/<stem>.json + traces/<mode>/<stem>.pipeview.txt.gz
for hits, errors/<idx>.log for failures, driver.log (start/end, every test, every
error with traceback). Resumable: finished idx in results.jsonl are skipped.
"""
import argparse, gzip, json, os, random, re, shutil, signal, subprocess, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "sitecustom"
_lock = threading.Lock()
_stop = threading.Event()


def load_jsonc(p: Path) -> dict:
    txt = re.sub(r"/\*.*?\*/", "", p.read_text(), flags=re.S)
    txt = re.sub(r"//[^\n]*", "", txt)
    return json.loads(txt)


def log(out: Path, msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    with _lock:
        with open(out / "driver.log", "a") as f:
            f.write(line + "\n")
    print(line, flush=True)


def build_order(testset_model: Path, modes, seed: int):
    pairs = []
    for m in modes:
        a = {p.stem for p in (testset_model / m / "asm").glob("inst-*.s")}
        n = {p.name[:-len(".ann.json")] for p in (testset_model / m / "ann").glob("inst-*.ann.json")}
        pairs += [(m, s) for s in sorted(a & n)]
    pairs.sort()
    random.Random(seed).shuffle(pairs)
    return pairs


def run_one(idx, mode, stem, cfg, args, out: Path, testset_model: Path):
    wd = out / "work" / f"{idx:06d}"
    shutil.rmtree(wd, ignore_errors=True)
    s_asm = wd / "stage" / args.model / mode / "asm"
    s_ann = wd / "stage" / args.model / mode / "ann"
    s_asm.mkdir(parents=True)
    s_ann.mkdir(parents=True)
    (s_asm / f"{stem}.s").symlink_to(testset_model / mode / "asm" / f"{stem}.s")
    (s_ann / f"{stem}.ann.json").symlink_to(testset_model / mode / "ann" / f"{stem}.ann.json")
    pc = json.loads(json.dumps(cfg))
    pc["paths"]["testset_dir"] = str(wd / "stage")
    pc["paths"]["results_dir"] = str(wd / "res")
    pc["paths"]["results_name"] = "out"
    pc["speculation"]["branch_modes"] = [mode]
    pc["gem5"]["jobs"] = 1
    pc.setdefault("pipeline", {})["keep_tmp"] = True
    pcp = wd / "pass_cfg.json"
    pcp.write_text(json.dumps(pc, indent=1))
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SITE) + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    glog = wd / "gem5_rusage.jsonl"
    env["TIMING_GEM5_LOG"] = str(glog)
    row = dict(idx=idx, mode=mode, stem=stem, t_start=time.time())
    t0 = time.monotonic()
    with open(wd / "pipeline.log", "w") as lf:
        p = subprocess.Popen([sys.executable, "pipeline.py", "gem5", "--model", args.model,
                              "--config", str(pcp), "--force"], cwd=args.code_root,
                             stdout=lf, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        try:
            _, sts, ru = os.wait4(p.pid, 0)
        except BaseException:
            os.killpg(p.pid, signal.SIGKILL)
            raise
    row["wall_s"] = round(time.monotonic() - t0, 3)
    row["total_cpu_s"] = round(ru.ru_utime + ru.ru_stime, 3)
    row["pipeline_rc"] = os.WEXITSTATUS(sts) if os.WIFEXITED(sts) else -1
    g = [json.loads(l) for l in glog.read_text().splitlines()] if glog.exists() else []
    row["n_gem5"] = len(g)
    row["gem5_cpu_s"] = round(sum(x["utime_s"] + x["stime_s"] for x in g), 3)
    row["gem5_wall_s"] = round(sum(x["wall_s"] for x in g), 3)
    row["gem5_rc"] = [x["rc"] for x in g]
    wr = wd / "res" / "out" / mode / "window-results.json"
    rec = None
    try:
        recs = json.loads(wr.read_text())
        rec = next((r for r in recs if r.get("name") == stem), None)
    except Exception:
        pass
    raw = None
    for rf in sorted((wd / "res" / "out" / mode / "sweep" / "raw_results").glob("*.json")):
        try:
            for r in json.loads(rf.read_text()):
                if r.get("name") == stem:
                    raw = r
        except Exception:
            pass
    if rec is None and raw is not None:
        rec = raw
    row["status"] = (rec or {}).get("status", "missing")
    row["hit"] = bool((rec or {}).get("issued_in_window"))
    if raw is not None:
        row["kind"] = raw.get("xmit_kind")
        row["terms_fired"] = raw.get("terms_fired")
        row["error"] = (raw.get("error") or "")[:300] or None
        row["cache_setup"] = raw.get("cache_setup")
    workdir = Path(raw["workdir"]) if raw and raw.get("workdir") else None
    if workdir and workdir.exists() and not (out / "config.ini").exists():
        for ci in workdir.rglob("config.ini"):   # one gem5 config.ini per campaign, for the full_configs.md check
            shutil.copy(ci, out / "config.ini")
            break
    if row["hit"] and raw is not None:
        rd = out / "raw" / mode
        rd.mkdir(parents=True, exist_ok=True)
        (rd / f"{stem}.json").write_text(json.dumps(raw))
        if workdir and workdir.exists():
            td = out / "traces" / mode
            td.mkdir(parents=True, exist_ok=True)
            for pv in workdir.rglob("pipeview.txt"):
                with open(pv, "rb") as fi, gzip.open(td / f"{stem}.pipeview.txt.gz", "wb") as fo:
                    shutil.copyfileobj(fi, fo)
                row["trace"] = str(td / f"{stem}.pipeview.txt.gz")
                break
    if row["status"] != "ok" or row["pipeline_rc"] != 0:
        ed = out / "errors"
        ed.mkdir(exist_ok=True)
        shutil.copy(wd / "pipeline.log", ed / f"{idx:06d}_{mode}_{stem}.log")
    if workdir and workdir.exists() and str(workdir).startswith(("/tmp", str(wd), "/tests")) and "stage" not in workdir.parts:
        shutil.rmtree(workdir, ignore_errors=True)
    if not args.keep_work:
        shutil.rmtree(wd, ignore_errors=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code-root", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20261109)
    ap.add_argument("--n", type=int, required=True, help="test budget (first n of the order)")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--parallel", type=int, default=2)
    ap.add_argument("--max-hours", type=float, default=24.0)
    ap.add_argument("--keep-work", action="store_true")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfgp = Path(args.config) if Path(args.config).is_absolute() else Path(args.code_root) / args.config
    cfg = load_jsonc(cfgp)
    tdir = cfg["paths"]["testset_dir"]
    testset_model = (Path(tdir) if Path(tdir).is_absolute() else Path(args.code_root) / tdir) / args.model
    modes = cfg["speculation"]["branch_modes"]
    log(out, f"START config={cfgp} model={args.model} seed={args.seed} n={args.n} start={args.start} "
             f"parallel={args.parallel} loadavg={os.getloadavg()} pid={os.getpid()}")
    shutil.copy(cfgp, out / "run_config.jsonc")
    of = out / "order.tsv"
    if of.exists():
        order = [tuple(l.split("\t")[1:3]) for l in of.read_text().splitlines()]
    else:
        order = build_order(testset_model, modes, args.seed)
        of.write_text("".join(f"{i}\t{m}\t{s}\n" for i, (m, s) in enumerate(order)))
        log(out, f"order written: {len(order)} (mode,stem) pairs, random.Random({args.seed}).shuffle of the sorted list")
    done = set()
    rj = out / "results.jsonl"
    if rj.exists():
        for l in rj.read_text().splitlines():
            try:
                done.add(json.loads(l)["idx"])
            except Exception:
                pass
    todo = [(i, *order[i]) for i in range(args.start, min(args.n, len(order))) if i not in done]
    log(out, f"{len(done)} already done, {len(todo)} to run")
    deadline = time.time() + args.max_hours * 3600
    nhit = 0
    with ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {}
        it = iter(todo)

        def submit_next():
            if time.time() > deadline:
                return False
            try:
                i, m, s = next(it)
            except StopIteration:
                return False
            futs[ex.submit(run_one, i, m, s, cfg, args, out, testset_model)] = (i, m, s)
            return True

        for _ in range(args.parallel):
            submit_next()
        while futs:
            for f in as_completed(list(futs)):
                i, m, s = futs.pop(f)
                try:
                    row = f.result()
                    with _lock:
                        with open(rj, "a") as fo:
                            fo.write(json.dumps(row) + "\n")
                    nhit += row["hit"]
                    log(out, f"idx={i} {m}/{s} status={row['status']} hit={row['hit']} kind={row.get('kind')} "
                             f"gem5_cpu={row['gem5_cpu_s']}s total_cpu={row['total_cpu_s']}s wall={row['wall_s']}s "
                             f"n_gem5={row['n_gem5']} terms={row.get('terms_fired')}")
                except Exception:
                    log(out, f"ERROR idx={i} {m}/{s}:\n{traceback.format_exc()}")
                submit_next()
                break
    log(out, f"END hits_this_session={nhit} loadavg={os.getloadavg()}")


if __name__ == "__main__":
    main()
