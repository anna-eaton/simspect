#!/usr/bin/env python3
"""
diag_ld_cache_reach.py — shared diagnostic for check_ld hits.

WHY THIS EXISTS
---------------
`check_ld` scores a load as leaking when its LSQ "Executing load" tick lands
inside the speculative window. But "Executing load" is emitted at the TOP of the
load path, *before* the defense decides whether to actually expose the access to
the cache. So a load can be scored a hit yet never make a real (architecturally
visible) cache access:

  * recon / DoM style:   "Executing load" then bounced (delay_unit) — no packet,
                         never completed.  FALSE POSITIVE.
  * InvisibleSpec style:  sent as a *spec read* into the spec buffer, not a
                          visible cache fill ("send a spec read for inst ...").
                          FALSE POSITIVE.
  * real leak (cache):    a normal read packet actually goes to cache
                          ("successfully sent out packet(s) for inst [sn:N]").
  * real leak (SLF):      store-to-load forwarding — the load OBTAINS its data
                          from a store in the LSQ and COMPLETES with NO packet.
                          A cache-packet-only bar misses this; it is a REAL leak.
                          The data-obtained discriminator is completion, not the
                          packet — check_ld gates on (packet OR pipeview
                          'complete'). This trace-only diagnostic cannot see the
                          pipeview 'complete' stage, so it bucket SLF loads as
                          `executed_no_packet`; do NOT treat that bucket as a
                          pure false positive — cross-check completion (the
                          checker now does this inline).

This diagnostic re-runs gem5 (identically to the checker — same binary / se.py /
scheme / flags / env) and classifies each xmit load's *true cache fate* from the
LSQUnit trace, separating REAL visible cache accesses from check_ld false
positives. It is build-agnostic: it keys on the packet/spec-read markers, which
exist across the recon / STT / SPT builds.

This is the cross-cutting counterpart to the per-results `diagnostics/` scripts:
because the check_ld over-count is a *checker* artifact (not defense-specific),
EVERY check_ld consumer should run its hits through this before trusting the
count. See claudelog 2026-06-02 (reconbugs check_ld false positive; designconsultant
inst-047231 real cache access).

USAGE
-----
  # classify just the hits of a finished sweep, using that run's config for env:
  python3 STAGE3_gem5/diag_ld_cache_reach.py <dir-with-.s-and-.ann.json> \
      --config results/<name>/run_config.jsonc \
      --hits-from results/<name>/<mode>/window-results.json \
      --jobs 16 --out cache_reach.json

  # or set SIMSPECT_* env yourself (as when invoking check_ld by hand) and omit --config.

FATE values:  reached_cache (REAL) | spec_read_only | executed_no_packet |
              never_executed | no_xmit_pc | error
`real_access` is True only for fate == reached_cache.
"""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def _apply_config_env(config_path: Path) -> None:
    """Populate SIMSPECT_* env from a run_config.jsonc, reusing pipeline's bridge,
    so the diagnostic runs gem5 exactly as that campaign's checker did. Scheme is
    a gem5_common module global (not env), so we stash it in SIMSPECT_SCHEME and
    diagnose_one applies it after import (survives fork to worker processes)."""
    sys.path.insert(0, str(REPO))
    import pipeline  # noqa: E402  (the engine; reused, not modified)
    cfg = pipeline.load_config(config_path)
    env = pipeline._build_gem5_env(cfg.get("gem5", {}), cfg.get("speculation", {}))
    os.environ.update({k: str(v) for k, v in env.items()})
    scheme = cfg.get("gem5", {}).get("scheme")
    if scheme is not None:
        os.environ["SIMSPECT_SCHEME"] = str(scheme)
    # The sweep's branch-resolve stalls are NOT env vars — they are injected into
    # each test's annotation (pipeline._inject_stalls) and read by gem5 via
    # --branch-ann-file. A hit only reproduces under the SAME stall regime that
    # produced it (CLAUDE.md), so forward the whole sweep block; diagnose_one
    # rebuilds the grid and reruns every grid point. Stash as JSON in env so it
    # survives fork to worker processes.
    os.environ["SIMSPECT_SWEEP_CFG"] = json.dumps(cfg.get("sweep", {}))


# ── trace classification ──────────────────────────────────────────────────────

_EXEC_RE = re.compile(
    r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+Executing load PC \(0x([0-9a-f]+)=>.*\[sn:(\d+)\]")
_PKT_RE = re.compile(
    r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+successfully sent out packet\(s\) for inst \[sn:(\d+)\]")
_SPEC_RE = re.compile(
    r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+send a spec read for inst \[sn:(\d+)\]")
_SQUASH_RE = re.compile(
    r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+Load Instruction PC \(0x[0-9a-f]+=>.*squashed,\s*\[sn:(\d+)\]")


def classify_trace(trace_path: Path, xmit_pc: int) -> dict:
    """Return the xmit load's cache fate from a LSQUnit trace."""
    xmit_hex = f"{xmit_pc:x}"
    exec_sns = {}        # sn -> first execute tick (only for xmit_pc)
    pkt_sns = {}         # sn -> packet tick
    spec_sns = {}        # sn -> spec-read tick
    squash_sns = {}      # sn -> squash tick
    with open(trace_path, errors="replace") as f:
        for line in f:
            m = _EXEC_RE.match(line)
            if m and m.group(2) == xmit_hex:
                exec_sns.setdefault(int(m.group(3)), int(m.group(1)))
                continue
            m = _PKT_RE.match(line)
            if m:
                pkt_sns.setdefault(int(m.group(2)), int(m.group(1))); continue
            m = _SPEC_RE.match(line)
            if m:
                spec_sns.setdefault(int(m.group(2)), int(m.group(1))); continue
            m = _SQUASH_RE.match(line)
            if m:
                squash_sns.setdefault(int(m.group(2)), int(m.group(1)))

    if not exec_sns:
        return dict(fate="never_executed", real_access=False,
                    xmit_sns=[], packet_tick=None, spec_read_tick=None, squash_tick=None)

    # Pick the fate over all xmit-PC load instances (any real packet wins).
    reached = [(sn, pkt_sns[sn]) for sn in exec_sns if sn in pkt_sns]
    specd = [(sn, spec_sns[sn]) for sn in exec_sns if sn in spec_sns]
    if reached:
        sn, tick = sorted(reached, key=lambda x: x[1])[0]
        fate, real = "reached_cache", True
        pkt, spec = tick, None
        # A real cache packet went out -> the load touched cache -> REAL leak.
        # The load's own squash tick is INFORMATIVE ONLY, never a disqualifier:
        # a squashed speculative load that already sent its packet has leaked
        # (the cache state change is observable post-squash). We record whether
        # the packet preceded the squash for inspection, but real_access stays
        # True regardless. (The in-window check is the lc/fnc bound, applied by
        # check_ld; this diagnostic only answers "did it touch cache".)
        sq = squash_sns.get(sn)
        pre = (sq is not None and tick < sq)
        return dict(fate=fate, real_access=real, packet_before_squash=pre,
                    xmit_sns=sorted(exec_sns), packet_tick=tick,
                    spec_read_tick=None, squash_tick=sq)
    elif specd:
        sn, tick = sorted(specd, key=lambda x: x[1])[0]
        fate, real = "spec_read_only", False
        pkt, spec = None, tick
    else:
        sn = sorted(exec_sns)[0]
        fate, real = "executed_no_packet", False
        pkt, spec = None, None
    return dict(fate=fate, real_access=real, xmit_sns=sorted(exec_sns),
                packet_tick=pkt, spec_read_tick=spec,
                squash_tick=squash_sns.get(sn))


# ── per-test driver (mirrors gem5_common.process_one build/run path) ───────────

# fate ranking: a higher rank "wins" when aggregating over a test's stall grid
# (any grid point that reaches cache makes the whole test a real access).
_FATE_RANK = {"never_executed": 0, "executed_no_packet": 1,
              "spec_read_only": 2, "reached_cache": 3}


def _sweep_grids(ann: dict, stem: str):
    """Rebuild the campaign's stall grid for one test (list of stalls-dicts).
    Empty/absent sweep cfg → single empty grid point (raw-ann behavior)."""
    sweep = json.loads(os.environ.get("SIMSPECT_SWEEP_CFG", "{}") or "{}")
    if not sweep.get("enabled"):
        return [None], 0
    import pipeline  # the engine; reused, not modified
    resolved, _ = pipeline._classify_branches(ann)
    grid = pipeline._grid_points(
        resolved, sweep.get("points", [0]),
        unresolved_points=sweep.get("unresolved_points"),
        max_grid=sweep.get("max_grid"),
        seed=(hash(stem) & 0xffffffff))
    return grid, int(sweep.get("unresolved_stall_cycles", 0))


def diagnose_one(args):
    s_path, ann_path = args
    import gem5_common as gc  # imported AFTER env is set in main()
    if "SIMSPECT_SCHEME" in os.environ:
        gc._scheme = int(os.environ["SIMSPECT_SCHEME"])
    name = s_path.stem
    workdir = Path(__import__("tempfile").mkdtemp(prefix=f"diag_{name}_"))
    rec = dict(name=name, status="ok", xmit_pc=None, fate=None,
               real_access=None, error=None)
    try:
        parts = gc.load_annotation(ann_path)
        xmit = parts["xmit"]
        rec["xmit_kind"] = xmit.get("kind", "")
        binary = gc.build_binary(s_path, workdir)
        xmit_pc = gc.resolve_pc(binary, name, xmit)
        fnc_pc = gc.resolve_pc(binary, name, parts["fnc"])
        if xmit_pc is None:
            rec.update(status="warn", fate="no_xmit_pc", real_access=False)
            return rec
        rec["xmit_pc"] = hex(xmit_pc)

        import pipeline
        full_ann = json.loads(Path(ann_path).read_text())
        grid, unresolved_stall = _sweep_grids(full_ann, name)
        best, n_reached = None, 0
        for gi, stalls in enumerate(grid):
            if stalls is None:           # no-sweep fallback: raw ann
                run_ann = ann_path
            else:
                inj = pipeline._inject_stalls(full_ann, stalls, unresolved_stall)
                run_ann = workdir / f"ann_g{gi}.json"
                run_ann.write_text(json.dumps(inj))
            trace = gc.run_gem5(binary, workdir, ann_path=run_ann, fnc_pc=fnc_pc)
            res = classify_trace(trace, xmit_pc)
            if res.get("real_access"):
                n_reached += 1
            if best is None or _FATE_RANK.get(res["fate"], 0) > _FATE_RANK.get(best["fate"], 0):
                best = res
        rec.update(best)
        rec["grid_size"] = len(grid)
        rec["grid_reached_cache"] = n_reached
    except Exception as e:  # incl. subprocess.CalledProcessError
        rec.update(status="error", fate="error", real_access=False,
                   error=str(e)[-300:])
    finally:
        __import__("shutil").rmtree(workdir, ignore_errors=True)
    return rec


def _hit_stems(hits_from: Path) -> set:
    data = json.loads(Path(hits_from).read_text())
    return {r["name"] for r in data if r.get("issued_in_window") is True}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("--config", type=Path, default=None,
                    help="run_config.jsonc → SIMSPECT_* env (else read env directly)")
    ap.add_argument("--hits-from", type=Path, default=None,
                    help="window-results.json: only diagnose its issued_in_window hits")
    ap.add_argument("--scheme", type=int, default=None,
                    help="override scheme (default: from config/env)")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.config:
        _apply_config_env(args.config)
    if args.scheme is not None:
        os.environ["SIMSPECT_SCHEME"] = str(args.scheme)
    sys.path.insert(0, str(HERE))

    stems = None
    if args.hits_from:
        stems = _hit_stems(args.hits_from)
    pairs = []
    for s in sorted(args.input_dir.glob("*.s")):
        if stems is not None and s.stem not in stems:
            continue
        ann = args.input_dir / (s.stem + ".ann.json")
        if ann.exists():
            # absolute: run_gem5 runs with cwd=GEM5_DIR, so a relative
            # --branch-ann-file / .s would not resolve.
            pairs.append((s.resolve(), ann.resolve()))

    print(f"diagnosing {len(pairs)} test(s)"
          + (f" (hits from {args.hits_from.name})" if args.hits_from else "")
          + f"  jobs={args.jobs}", file=sys.stderr)

    results = []
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            futs = [ex.submit(diagnose_one, p) for p in pairs]
            for fu in as_completed(futs):
                results.append(fu.result())
    else:
        for p in pairs:
            results.append(diagnose_one(p))

    from collections import Counter
    fates = Counter(r["fate"] for r in results)
    real = sum(1 for r in results if r.get("real_access"))
    pre  = sum(1 for r in results if r.get("packet_before_squash"))
    post = real - pre
    print(f"\nfate breakdown: {dict(fates)}", file=sys.stderr)
    print(f"REAL visible cache accesses: {real} / {len(results)}  "
          f"(rest are check_ld false positives)", file=sys.stderr)
    print(f"  all {real} are real leaks (touched cache); squash timing is "
          f"informational: {pre} packet-before-squash, {post} packet-after-squash",
          file=sys.stderr)
    if args.out:
        args.out.write_text(json.dumps(results, indent=2))
        print(f"written: {args.out}", file=sys.stderr)
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
