#!/usr/bin/env python3
"""
testrun.py — SimSpect test executor (the CONSUMER half of the pipeline).

A gem5-ONLY sweep watcher (same mechanism as results/_sweep_watcher.py) with
two additions:

  1. Results are PARTITIONED BY TRANSMITTER TYPE — each test's records land in
     results/<name>__<ts>/<mode>/<kind>/window-results.json (kind ∈ ld / br_x /
     other_x), so ld vs br_x hits can be inspected separately without joining
     records back to the annotations.
  2. The campaign dir is TIMESTAMPED (results/<name>__<ts>/) with a stable
     results/<name>__latest symlink, so every run is dated and a manifest
     records which build/scheme produced it.

Polls a testset still being produced by testsetgen.py, runs gem5 on each newly
ready test (asm ∩ ann) via pipeline.py's gem5 phase, and merges per kind. Pure
consumer: never compiles, never writes into testsets/.

Run one per build/scheme (each --config points at its own gem5 binary); launch
several against the same --model to compare defenses concurrently. This file is
a standalone duplicate of the watcher so the in-flight _sweep_watcher.py runs
are never touched.

Usage:
    python3 testrun.py --config results/SPT_6_oneLP_fence/run_config.jsonc \
                       --model SPT_6_oneLP [--interval 300] [--max-new 2000]
                       [--resume] [--once]
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/tests/simspect")
sys.path.insert(0, str(ROOT / "STAGE3_gem5"))
from gem5_common import sample_keep

KIND_FALLBACK = "other_x"   # bucket for missing/unreadable xmit.kind


def load_jsonc(p: Path) -> dict:
    return json.loads(re.sub(r"//.*", "", p.read_text()))


def ready_stems(testset_model: Path, mode: str, sample_frac: float = 1.0) -> set:
    asm = testset_model / mode / "asm"
    ann = testset_model / mode / "ann"
    if not asm.is_dir() or not ann.is_dir():
        return set()
    a = {p.stem for p in asm.glob("inst-*.s")}
    n = {p.name[:-len(".ann.json")] for p in ann.glob("inst-*.ann.json")}
    ready = a & n
    if sample_frac < 1.0:
        ready = {s for s in ready if sample_keep(s, sample_frac)}
    return ready


def stem_kind(ann_dir: Path, stem: str) -> str:
    try:
        d = json.loads((ann_dir / f"{stem}.ann.json").read_text())
        return d.get("xmit", {}).get("kind") or KIND_FALLBACK
    except Exception:
        return KIND_FALLBACK


def done_stems(mode_dir: Path) -> set:
    """Union of stems already recorded across every per-kind window-results."""
    done: set = set()
    if not mode_dir.is_dir():
        return done
    for wr in mode_dir.glob("*/window-results.json"):
        try:
            done |= {r["name"] for r in json.loads(wr.read_text())}
        except Exception:
            pass
    return done


def merge_kind(kind_dir: Path, recs: list) -> tuple:
    kind_dir.mkdir(parents=True, exist_ok=True)
    f = kind_dir / "window-results.json"
    existing = []
    if f.exists():
        try:
            existing = json.loads(f.read_text())
        except Exception:
            existing = []
    by_name = {r["name"]: r for r in existing}
    for r in recs:                              # new wins on dup
        by_name[r["name"]] = r
    merged = sorted(by_name.values(), key=lambda r: r["name"])
    f.write_text(json.dumps(merged, indent=2))
    hits = [r["name"] for r in merged if r.get("issued_in_window")]
    (kind_dir / "window-hits.txt").write_text(
        ("\n".join(hits) + "\n") if hits else "")
    return len(merged), len(hits)


def run_pass(cfg: dict, model: str, mode: str, results_base: Path,
             max_new: int) -> int:
    """One mode, one batch. Returns number of NEW tests processed."""
    testset_dir   = cfg["paths"]["testset_dir"]
    campaign      = results_base.name                      # <name>__<ts>
    testset_model = ROOT / testset_dir / model
    src_asm = testset_model / mode / "asm"
    src_ann = testset_model / mode / "ann"
    mode_dir = results_base / mode
    mode_dir.mkdir(parents=True, exist_ok=True)

    sample_frac = float(cfg.get("gem5", {}).get("sample_fraction", 1.0))
    new = sorted(ready_stems(testset_model, mode, sample_frac)
                 - done_stems(mode_dir))
    if not new:
        return 0
    batch = new[:max_new]

    # Stage just this batch as symlinks under the campaign dir (never touch
    # testsets/), then run pipeline.py's gem5 phase over the staged subset.
    stage_rel = f"results/{campaign}/_stage_{mode}"
    tmp_rel   = f"results/{campaign}/_tmp_{mode}"
    stage_root = ROOT / stage_rel
    tmp_root   = ROOT / tmp_rel
    for d in (stage_root, tmp_root):
        shutil.rmtree(d, ignore_errors=True)
    s_asm = stage_root / model / mode / "asm"
    s_ann = stage_root / model / mode / "ann"
    s_asm.mkdir(parents=True, exist_ok=True)
    s_ann.mkdir(parents=True, exist_ok=True)
    for st in batch:
        (s_asm / f"{st}.s").symlink_to(src_asm / f"{st}.s")
        (s_ann / f"{st}.ann.json").symlink_to(src_ann / f"{st}.ann.json")

    pass_cfg = json.loads(json.dumps(cfg))
    pass_cfg["paths"]["testset_dir"]  = stage_rel
    pass_cfg["paths"]["results_dir"]  = tmp_rel
    pass_cfg["paths"]["results_name"] = "out"
    pass_cfg["speculation"]["branch_modes"] = [mode]
    pass_cfg_path = results_base / f"_pass_cfg_{mode}.json"
    pass_cfg_path.write_text(json.dumps(pass_cfg, indent=2))

    print(f"[testrun {time.strftime('%H:%M:%S')}] {model}/{mode}: "
          f"{len(batch)} new (of {len(new)} pending) → gem5", flush=True)
    r = subprocess.run(
        [sys.executable, "pipeline.py", "gem5", "--model", model,
         "--config", str(pass_cfg_path.relative_to(ROOT)), "--force"],
        cwd=str(ROOT), capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[testrun] pipeline gem5 FAILED ({model}/{mode}):\n"
              f"{r.stdout[-1500:]}\n{r.stderr[-1500:]}", flush=True)
        return 0

    out_rs = tmp_root / "out" / mode
    wr = out_rs / "window-results.json"
    recs = json.loads(wr.read_text()) if wr.exists() else []

    # Partition records by transmitter kind (read from each stem's annotation).
    by_kind: dict = {}
    for rec in recs:
        by_kind.setdefault(stem_kind(src_ann, rec["name"]), []).append(rec)
    summary = []
    for k in sorted(by_kind):
        n_tot, n_hit = merge_kind(mode_dir / k, by_kind[k])
        summary.append(f"{k} {n_hit}/{n_tot}")

    # Relocate sweep sidecars (shared across kinds).
    raw = out_rs / "sweep" / "raw_results"
    if raw.is_dir():
        dst = mode_dir / "_sweep_raw"
        dst.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d%H%M%S")
        for rf in raw.glob("*.json"):
            shutil.move(str(rf), str(dst / f"{ts}_{rf.name}"))

    shutil.rmtree(stage_root, ignore_errors=True)
    shutil.rmtree(tmp_root,   ignore_errors=True)
    pass_cfg_path.unlink(missing_ok=True)
    print(f"[testrun {time.strftime('%H:%M:%S')}] {model}/{mode}: "
          f"+{len(recs)} → " + " | ".join(summary), flush=True)
    return len(batch)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--model",  required=True)
    ap.add_argument("--interval", type=int, default=300)
    ap.add_argument("--max-new",  type=int, default=2000)
    ap.add_argument("--resume", action="store_true",
                    help="reuse results/<name>__latest instead of a new campaign")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()

    cfg_path = ROOT / a.config if not os.path.isabs(a.config) else Path(a.config)
    cfg = load_jsonc(cfg_path)
    modes = cfg["speculation"]["branch_modes"]
    expected = int(cfg.get("alloy", {}).get("max_instances", 0))
    testset_model = ROOT / cfg["paths"]["testset_dir"] / a.model
    results_name = cfg["paths"]["results_name"]

    latest = ROOT / "results" / f"{results_name}__latest"
    if a.resume and latest.exists():
        results_base = latest.resolve()
        print(f"[testrun] resuming campaign {results_base}", flush=True)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        results_base = ROOT / "results" / f"{results_name}__{ts}"
        results_base.mkdir(parents=True, exist_ok=True)
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(results_base.name)        # relative, within results/
        (results_base / "manifest.json").write_text(json.dumps({
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": a.model,
            "results_name": results_name,
            "gem5_binary": cfg.get("gem5", {}).get("binary"),
            "gem5_extra_args": cfg.get("gem5", {}).get("extra_args"),
            "config": str(cfg_path),
        }, indent=2))
        print(f"[testrun] campaign {results_base}", flush=True)

    while True:
        progressed = 0
        for m in modes:
            progressed += run_pass(cfg, a.model, m, results_base, a.max_new)
        if a.once:
            break
        complete = expected > 0 and all(
            len(list((testset_model / m / "asm").glob("inst-*.s"))) >= expected
            for m in modes)
        if complete and progressed == 0:
            print(f"[testrun {time.strftime('%H:%M:%S')}] testset complete and "
                  f"no new tests — done.", flush=True)
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
