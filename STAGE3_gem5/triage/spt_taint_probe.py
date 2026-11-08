#!/usr/bin/env python3
"""Re-run hit tests on gem5-spt and read SPT's own taint decisions (2026-11-07).

Reproduces each hit exactly as its campaign ran it (the campaign's run_config
env, sweep grid point 0 = resolved stalls 0 and unresolved stall from the
config, or the given grid index) and reports what gem5-spt itself decided:
  pending   every Commit-trace "(Lazy) A branch|load mispredic... is made
            pending" line (commit_impl.hh:944: printed iff the squashing
            instruction isArgsTainted() and is not yet unsquashable). A
            mispredicting branch with NO pending line had untainted arguments
            when it squashed, by gem5-spt's own check.
  stats     the SPT taint counters from stats.txt (VPUntaints, untaint and
            stalled-squash counts).
gem5-spt's per-instruction taint tracking (--trackInstsFile) is not used: its
print helper asserts on any full-width register (regfile.hh:280,
`size + offs < taintVec.size()`), so it aborts on the first movq.

    python3 spt_taint_probe.py --config <run_config.jsonc> --testdir <testset>/<mode> \
        --stems inst-1[:grid] inst-2[:grid] ... --jobs 8 --out probe.json [--keep]

`:grid` is the sweep grid index of the hit (the gridNNNN tag of its raw file);
default 0.

The checker verdict of the re-run is recorded too, so a probe that no longer
reproduces the hit is visible (`reproduced` False).
"""
import argparse, json, os, re, sys, tempfile, shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "STAGE3_gem5"))

_EV = [  # (kind, regex on stdout); groups: cycle, addr, seq
    ("inserted", re.compile(r"^\[(\w+)\] (\w+)\.(\d+) inserted into ROB")),
    ("dest_tainted", re.compile(r"^\[(\w+)\] (\w+)\.(\d+) dest tainted due to (.*)")),
    ("fwd_untaint_marked", re.compile(r"^\[(\w+)\] (\w+)\.(\d+) dest regs marked for untainting via forward propagation")),
    ("bwd_untaint_marked", re.compile(r"^\[(\w+)\] (\w+)\.(\d+) .*src regs marked for untainting via backward propagation")),
    ("unsquashable", re.compile(r"^\[(\w+)\] (\w+)\.(\d+) is now unsquashable")),
    ("vp_untaint", re.compile(r"^\[(\w+)\] untainting src reg (\S+) via (load|store) (\w+)\.(\d+) because it reached VP")),
    ("vp_reached", re.compile(r"^\[(\w+)\] (load|store) (\w+)\.(\d+) has reached VP")),
    ("nonmem_vp_untaint", re.compile(r"^\[(\w+)\] .*non-memory transmitter.*?(\w+)\.(\d+)")),
]
_PENDING = re.compile(r"^\s*(\d+):.*\(Lazy\) A (branch|load) mispredic\w* \[sn:(\d+),0x\w+\] PC \(0x([0-9a-f]+)=>")


def _env(config):
    import pipeline
    cfg = pipeline.load_config(Path(config))
    env = pipeline._build_gem5_env(cfg.get("gem5", {}), cfg.get("speculation", {}))
    env = {k: str(v) for k, v in env.items()}
    extra = env.get("SIMSPECT_GEM5_EXTRA", "")
    sc = cfg.get("gem5", {}).get("scheme")
    if sc is not None:
        env["SIMSPECT_SCHEME"] = str(sc)
    return env, int(cfg.get("sweep", {}).get("unresolved_stall_cycles", 0) or 0), cfg.get("sweep", {})


def probe_one(args):
    stem, testdir, config, keep = args
    stem, _, gidx = stem.partition(":")          # "inst-N[:grid_index]"
    gidx = int(gidx or 0)
    env, unres, sweep = _env(config)
    os.environ.update(env)
    import gem5_common as gc
    import pipeline
    if "SIMSPECT_SCHEME" in os.environ:
        gc._scheme = int(os.environ["SIMSPECT_SCHEME"])
    rec = dict(stem=stem, grid=gidx, error=None)
    wd = Path(tempfile.mkdtemp(prefix=f"sptprobe_{stem}_"))
    saved = {}

    def _run_capture(cmd):
        import subprocess
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(gc.GEM5_DIR),
                           timeout=gc.GEM5_TIMEOUT_S)
        saved["stdout"] = p.stdout.decode(errors="replace")
        if p.returncode != 0:
            raise subprocess.CalledProcessError(p.returncode, cmd, p.stdout, p.stderr)
    try:
        gc._run_bounded = _run_capture
        ann = json.loads((Path(testdir) / "ann" / f"{stem}.ann.json").read_text())
        staged = wd / f"{stem}.ann.json"
        # Same grid as pipeline._enumerate_grid_for_corpus for this test.
        import zlib
        resolved, _ = pipeline._classify_branches(ann)
        grid = pipeline._grid_points(resolved, sweep.get("points", [0]),
                                     unresolved_points=sweep.get("unresolved_points"),
                                     max_grid=sweep.get("max_grid"), seed=zlib.crc32(stem.encode()))
        rec["stalls"] = grid[gidx]
        staged.write_text(json.dumps(pipeline._inject_stalls(ann, grid[gidx], unres)))
        s_path = wd / f"{stem}.s"
        shutil.copy(Path(testdir) / "asm" / f"{stem}.s", s_path)
        kind = ann.get("xmit", {}).get("kind")
        mod = __import__({"br_x": "check_br", "other_x": "check_other"}.get(kind, "check_ld"))
        fn = getattr(mod, {"br_x": "check_br", "other_x": "check_other"}.get(kind, "check_ld"))
        r = gc.process_one(s_path, staged, fn, keep_tmp=True)
        rec.update(reproduced=bool(r.get("issued_in_window")), status=r.get("status"), gem5_error=r.get("error"),
                   criteria=r.get("criteria"), xmit_pc=r.get("xmit_pc"), xmit_signal=r.get("xmit_signal"),
                   br_events=r.get("br_events"))
        work = Path(r.get("workdir", ""))
        trace = work / "m5out" / gc.GEM5_DBG_FILE
        pend = []
        if trace.exists():
            with open(trace) as f:
                for ln in f:
                    m = _PENDING.match(ln)
                    if m:
                        pend.append(dict(tick=int(m.group(1)), what=m.group(2), seq=int(m.group(3)),
                                         pc=hex(int(m.group(4), 16))))
        rec["pending"] = pend
        st = work / "m5out" / "stats.txt"
        if st.exists():
            rec["stats"] = {ln.split()[0]: ln.split()[1] for ln in st.read_text().splitlines()
                            if ln.strip() and not ln.startswith("-") and len(ln.split()) > 1
                            and re.search(r"ntaint|stalled|Tainted|VP", ln.split()[0])}
        ev = []
        for ln in saved.get("stdout", "").splitlines():
            for k, rx in _EV:
                m = rx.match(ln)
                if not m:
                    continue
                g = m.groups()
                if k == "vp_untaint":
                    ev.append(dict(k=k, cyc=int(g[0], 16), reg=g[1], via=g[2], pc=hex(int(g[3], 16)), seq=int(g[4])))
                elif k == "vp_reached":
                    ev.append(dict(k=k, cyc=int(g[0], 16), via=g[1], pc=hex(int(g[2], 16)), seq=int(g[3])))
                else:
                    e = dict(k=k, cyc=int(g[0], 16), pc=hex(int(g[1], 16)), seq=int(g[2]))
                    if k == "dest_tainted":
                        e["why"] = g[3]
                    ev.append(e)
                break
        rec["taint_events"] = ev
        if keep:
            (wd / "stdout.txt").write_text(saved.get("stdout", ""))
            rec["workdir"] = str(work)
        elif work.exists():
            shutil.rmtree(work, ignore_errors=True)
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[-400:]}"
    finally:
        if not keep:
            shutil.rmtree(wd, ignore_errors=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--testdir", required=True)
    ap.add_argument("--stems", nargs="+", required=True)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = []
    with ProcessPoolExecutor(a.jobs) as ex:
        futs = [ex.submit(probe_one, (s, a.testdir, a.config, a.keep)) for s in a.stems]
        for f in as_completed(futs):
            out.append(f.result())
            print(out[-1]["stem"], out[-1].get("reproduced"), out[-1].get("error"), flush=True)
    a.out.write_text(json.dumps(sorted(out, key=lambda r: r["stem"]), indent=1))


if __name__ == "__main__":
    main()
