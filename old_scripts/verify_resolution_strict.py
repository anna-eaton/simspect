#!/usr/bin/env python3
"""
verify_resolution_strict.py

Re-run a sample of ld-hit tests with keep_tmp=true so we get the per-test
pipeview, then read the unresolved branch's actual RESOLUTION cycle (=
its wrip micro-op's complete tick + unresolved_stall_cycles in ticks),
and check the strict invariant:

  xmit_complete < unresolved_branch_resolution

Where resolution time is the cycle the deferred broadcast event fires,
NOT the retire of the branch (retire happens ~1-2 cycles later).

We extract `complete` directly from the pipeview's last micro-op record
at the unresolved branch's PC, which is the wrip's execute-complete tick.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Dict, Tuple

ROOT = Path(__file__).parent
MODEL = "STT_6"
GEN = ROOT / "generated" / MODEL
ASM = GEN / "asm"
ANN = GEN / "ann"
SWEEP = GEN / "sweep"
RESULTS_CLEANED = GEN / "results_cleaned_ld"

SAMPLE_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 50
TICKS_PER_CYCLE = 500   # gem5 default for the X86O3CPU we run

# Pick STALL value to use (matches what STT_6 used in the sweep):
UNRESOLVED_STALL_CYCLES = 5000


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from STAGE3_gem5.gem5_common import parse_pipeview, best_record  # type: ignore

    # Pick a random sample of ld-hit stems
    hits_f = RESULTS_CLEANED / "window-hits.txt"
    if not hits_f.exists():
        sys.exit(f"missing {hits_f}; run investigate_br_hits.py STT_6 ld first")
    all_hits = [s for s in hits_f.read_text().splitlines() if s]
    random.seed(0)
    sample = random.sample(all_hits, min(SAMPLE_SIZE, len(all_hits)))
    print(f"sampling {len(sample)} of {len(all_hits)} ld-hit tests")

    # Per ld test, find ONE triggering grid point from the sidecar and run
    # gem5 with that variant's ann.json. We need the variant's stall config to
    # match what triggered.
    workroot = Path("/tmp/verify_resolution_strict")
    if workroot.exists():
        shutil.rmtree(workroot)
    workroot.mkdir()

    cases: List[Tuple[str, Dict[int, int]]] = []
    for stem in sample:
        sc = json.loads((SWEEP / f"{stem}_sweep.json").read_text())
        triggered = sc.get("triggered_points", [])
        if not triggered: continue
        # Use first triggering grid point
        stalls_dict = {int(k): int(v) for k, v in triggered[0].items()}
        cases.append((stem, stalls_dict))

    print(f"  {len(cases)} cases to run\n")

    # For each, build a per-test workdir and run gem5
    gem5 = "/work/gem5-recon-modded/build/X86/gem5.opt"
    se_script = "/work/gem5-recon-modded/configs/example/se.py"

    results = []
    for i, (stem, stalls_dict) in enumerate(cases, 1):
        wd = workroot / stem
        wd.mkdir()
        # Copy .s
        s_path = ASM / f"{stem}.s"
        shutil.copy(s_path, wd / s_path.name)
        # Build ann.json with these stalls injected
        ann_orig = json.loads((ANN / f"{stem}.ann.json").read_text())
        for entry in ann_orig.get("annotations", []):
            pc = entry.get("branch_pc")
            mode = entry.get("mode", "")
            if mode == "correctly_not_taken":
                entry["resolve_stall_cycles"] = stalls_dict.get(pc, 0)
            elif mode.startswith("mispredict_"):
                entry["resolve_stall_cycles"] = UNRESOLVED_STALL_CYCLES
        ann_path = wd / f"{stem}.ann.json"
        ann_path.write_text(json.dumps(ann_orig, indent=2))

        # Build run.json
        run_json = wd / "run.json"
        run_json.write_text(json.dumps({
            "cwd": "/work/gem5-recon-modded",
            "gem5_bin": "build/X86/gem5.opt",
            "debug": {"flags": ["O3PipeView"], "file": "pipeview.txt"},
            "config": {
                "script": "configs/example/se.py",
                "script_args": {
                    "cmd": str((wd / s_path.name).resolve()),
                    "cpu-type": "X86O3CPU",
                    "scheme": 2,
                    "caches": True,
                    "branch-ann-file": str(ann_path.resolve()),
                }
            }
        }))
        log = wd / "run.log"
        with log.open("w") as f:
            r = subprocess.run(
                ["python3", str(ROOT / "STAGE3_gem5" / "run_s.py"), str(run_json)],
                stdout=f, stderr=subprocess.STDOUT,
            )
        if r.returncode != 0:
            print(f"  [{i}/{len(cases)}] {stem}: gem5 FAILED")
            continue

        # Find pipeview output (run_s.py runs gem5 from its cwd, m5out goes there)
        pv = Path("/work/gem5-recon-modded/m5out/pipeview.txt")
        if not pv.exists():
            print(f"  [{i}/{len(cases)}] {stem}: missing pipeview"); continue
        # Copy locally before next run overwrites
        local_pv = wd / "pipeview.txt"
        shutil.copy(pv, local_pv)

        # Parse pipeview, find unresolved branch's wrip complete time
        by_pc = parse_pipeview(local_pv)
        unresolved_offsets = [
            e.get("x86_branch_offset")
            for e in ann_orig.get("annotations", [])
            if (e.get("mode") or "").startswith("mispredict_")
        ]
        # Use base from the m5out config or from objdump on the ELF
        # Easier: scan log for "--branch-ann-base=0x..."
        base = None
        for line in log.read_text().splitlines():
            if "--branch-ann-base=" in line:
                tok = line.split("--branch-ann-base=")[1].split()[0]
                base = int(tok, 16); break
        if base is None or not unresolved_offsets:
            print(f"  [{i}/{len(cases)}] {stem}: cant resolve base/unresolved")
            continue
        unresolved_abs = base + unresolved_offsets[0]
        recs = by_pc.get(unresolved_abs, [])
        if not recs:
            print(f"  [{i}/{len(cases)}] {stem}: no pipeview records at unresolved branch")
            continue

        # The wrip is the LAST micro-op (highest seqNum among ops at this PC).
        # best_record picks the one with latest retire — but we want the
        # complete time (execute-completion) of the wrip specifically.
        # Pick the record with max complete (the wrip's execute completes
        # last among the three micro-ops, since they run sequentially).
        wrip_rec = max(recs, key=lambda r: r["complete"])
        wrip_complete = wrip_rec["complete"]
        wrip_retire   = wrip_rec["retire"]

        # Predicted resolution tick = complete + stall_in_ticks
        resolution_tick = wrip_complete + UNRESOLVED_STALL_CYCLES * TICKS_PER_CYCLE

        # xmit complete from raw_results lookup — but easier: re-extract from pipeview
        xmit_offset = (ann_orig.get("xmit") or {}).get("x86_offset")
        if xmit_offset is None:
            print(f"  [{i}/{len(cases)}] {stem}: no xmit offset"); continue
        xmit_pc = base + xmit_offset
        xmit_recs = by_pc.get(xmit_pc, [])
        if not xmit_recs:
            print(f"  [{i}/{len(cases)}] {stem}: no pipeview at xmit pc")
            continue
        xmit_rec = best_record(xmit_recs)
        xmit_complete = xmit_rec["complete"]

        slack = resolution_tick - xmit_complete
        results.append(dict(stem=stem, xmit_complete=xmit_complete,
                            wrip_complete=wrip_complete, wrip_retire=wrip_retire,
                            resolution=resolution_tick, slack=slack,
                            stalls=stalls_dict))
        if i % 10 == 0:
            print(f"  [{i}/{len(cases)}] {stem}: "
                  f"xmit_complete={xmit_complete} wrip_complete={wrip_complete} "
                  f"resolution={resolution_tick} slack={slack}")

    # Summary
    print(f"\n=== {len(results)} cases verified ===")
    violations = [r for r in results if r["slack"] <= 0]
    print(f"  invariant violations (xmit_complete >= resolution): {len(violations)}")
    if violations:
        for v in violations[:5]: print(f"    {v}")

    # Slack distribution
    from collections import Counter
    buckets = Counter()
    for r in results:
        s = r["slack"]
        if s <= 0:          buckets["<=0"] += 1
        elif s < 1000:      buckets["0-1k"] += 1
        elif s < 10000:     buckets["1k-10k"] += 1
        elif s < 100000:    buckets["10k-100k"] += 1
        elif s < 1000000:   buckets["100k-1M"] += 1
        else:               buckets[">=1M"] += 1
    print("  resolution-cycle slack (resolution - xmit_complete) in ticks:")
    for k in ["<=0", "0-1k", "1k-10k", "10k-100k", "100k-1M", ">=1M"]:
        if buckets.get(k):
            print(f"    {k:>10}: {buckets[k]}")

    # gap between resolution and retire (sanity check)
    gaps = [r["wrip_retire"] - r["resolution"] for r in results
            if r["wrip_retire"] > 0]
    if gaps:
        print(f"\n  (sanity) wrip_retire − resolution (ticks): "
              f"min={min(gaps)}, median={sorted(gaps)[len(gaps)//2]}, max={max(gaps)}")


if __name__ == "__main__":
    main()
