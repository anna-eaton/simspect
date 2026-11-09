#!/usr/bin/env python3
"""stage2_sharded.py — parallel Stage 2 (XML -> .ll + ann) for one testset, sample stems first.

DRAFT TOOLING (2026-11-09, simspect-c8). pipeline.py's llvm phase runs ONE batch_generate.py over
every XML. This builds the exact same batch_generate.py command line as pipeline.py:phase_llvm
(same keys: instruction_tables, interleave, fpr, reg_naming, fanout_v2, store_separation,
branch_cond) and runs it over shards in parallel, writing into the same
<testset_dir>/<model>/<mode>/llvm. batch_generate seeds every test from its own stem
(zlib.crc32, batch_generate.py:109-131), so sharding changes no output.

Order: stems with gem5_common.sample_keep(stem, --first-fraction) first (so a sampled gem5 campaign
can start), then the rest. After each tier it runs `pipeline.py asm` (idempotent) so .s + resolved
.ann.json land for that tier. Already-generated stems are skipped (resumable).

Log: <testset>/<model>/stage2_sharded.log (start/end, per-shard rc, every batch_generate
[err]/[skip] line, stderr of failed shards). Run from the code root (the dir holding pipeline.py).

Usage:
  python3 stage2_sharded.py --config runconfigs/.../stage2_STT_6_fv2.jsonc --model STT_6_fv2 \
      --jobs 24 --first-fraction 0.02
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "STAGE3_gem5"))
import pipeline  # noqa: E402  (load_config / resolve, unchanged)
from gem5_common import sample_keep  # noqa: E402


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def bg_cmd(cfg, stage2, tables, xml_dir, llvm_dir, mode):
    """Mirror of pipeline.py:phase_llvm's command (keep in sync)."""
    cmd = [sys.executable, str(stage2 / "batch_generate.py"), str(xml_dir), "--out", str(llvm_dir),
           "--kind", "--instruction-tables", str(tables), "--mode", mode]
    il = cfg.get("interleave", {})
    if il:
        cmd += ["--interleave-config", json.dumps(il)]
    if cfg.get("fpr", {}).get("enabled"):
        cmd += ["--fpr-config", json.dumps(cfg["fpr"])]
    if cfg.get("reg_naming"):
        cmd += ["--reg-naming-config", json.dumps(cfg["reg_naming"])]
    if cfg.get("fanout_v2", {}).get("enabled"):
        cmd += ["--fanout-v2-config", json.dumps(cfg["fanout_v2"])]
    if cfg.get("store_separation", {}).get("enabled"):
        cmd += ["--store-separation-config", json.dumps(cfg["store_separation"])]
    if cfg.get("branch_cond", {}).get("from_alloy"):
        cmd += ["--branch-cond-config", json.dumps(cfg["branch_cond"])]
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--jobs", type=int, default=24)
    ap.add_argument("--shard-size", type=int, default=500)
    ap.add_argument("--first-fraction", type=float, default=0.02)
    a = ap.parse_args()

    cfg = pipeline.load_config(Path(a.config))
    ts = pipeline.resolve(cfg["paths"]["testset_dir"]) / a.model
    stage2 = pipeline.resolve(cfg["paths"]["stage2_dir"])
    tables = pipeline.resolve(cfg["paths"]["instruction_tables"])
    modes = cfg["speculation"]["branch_modes"]
    log = open(ts / "stage2_sharded.log", "a", buffering=1)

    def L(msg):
        log.write(f"{now()} {msg}\n")

    xmls = sorted((ts / "xml").glob("inst-*.xml"))
    first = [x for x in xmls if sample_keep(x.stem, a.first_fraction)]
    rest = [x for x in xmls if not sample_keep(x.stem, a.first_fraction)]
    L(f"START model={a.model} config={a.config} host={os.uname().nodename} xmls={len(xmls)} "
      f"first_tier={len(first)} (fraction {a.first_fraction}) jobs={a.jobs} modes={modes}")

    def run_shard(args):
        mode, shard, idx = args
        llvm_dir = ts / mode / "llvm"
        with tempfile.TemporaryDirectory(prefix="s2shard_") as tmp:
            for x in shard:
                os.symlink(x.resolve(), Path(tmp) / x.name)
            r = subprocess.run(bg_cmd(cfg, stage2, tables, tmp, llvm_dir, mode), cwd=str(stage2),
                               capture_output=True, text=True)
        bad = [l.strip() for l in r.stdout.splitlines() if "[err]" in l or "[skip]" in l]
        return mode, idx, len(shard), r.returncode, bad, (r.stderr[-4000:] if r.returncode else "")

    for tier_name, tier in (("first", first), ("rest", rest)):
        work = []
        for mode in modes:
            (ts / mode / "llvm").mkdir(parents=True, exist_ok=True)
            todo = [x for x in tier if not (ts / mode / "llvm" / (x.stem + ".ll")).exists()]
            for i in range(0, len(todo), a.shard_size):
                work.append((mode, todo[i:i + a.shard_size], i // a.shard_size))
        L(f"TIER {tier_name}: {sum(len(w[1]) for w in work)} (mode x xml) to generate in {len(work)} shards")
        with ThreadPoolExecutor(a.jobs) as ex:
            for mode, idx, n, rc, bad, err in ex.map(run_shard, work):
                L(f"shard {mode}#{idx} n={n} rc={rc} err_or_skip={len(bad)}")
                for b in bad:
                    L(f"  {mode}#{idx} {b}")
                if rc:
                    L(f"  {mode}#{idx} STDERR\n{err}")
        r = subprocess.run([sys.executable, "pipeline.py", "asm", "--model", a.model, "--config", a.config],
                           cwd=str(ROOT), capture_output=True, text=True)
        L(f"TIER {tier_name}: pipeline.py asm rc={r.returncode}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
        for mode in modes:
            n_ll = len(list((ts / mode / "llvm").glob("*.ll")))
            n_s = len(list((ts / mode / "asm").glob("*.s"))) if (ts / mode / "asm").exists() else 0
            L(f"TIER {tier_name} DONE {mode}: ll={n_ll} asm={n_s}")
    L("END")


if __name__ == "__main__":
    main()
