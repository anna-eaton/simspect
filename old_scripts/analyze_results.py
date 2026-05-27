#!/usr/bin/env python3
"""
analyze_results.py — summarize current sweep results across all runs.

For each populated results/<run>/[<mode>/] directory:
  * load window-results.json (post-merge aggregate)
  * categorize each hit's XML (SLF / LL / OtherLoad / BR / Other)
  * per category, count how many trigger at ALL grid points (full bypass)
    vs only some (STT partially mitigates)

Usage:
    python3 analyze_results.py                       # all runs
    python3 analyze_results.py --run STT_6_sttbuild  # one run
    python3 analyze_results.py --candidates-only     # only show non-BR hits
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from categorize_hits import parse_xml, categorize  # noqa: E402

# Map result-dir name → testset xml dir
TESTSET_OVERRIDES = {
    "STT_6":                       "STT_6",
    "STT_6_sttbuild":              "STT_6",
    "STT_6_interleave":            "STT_6_interleave",
    "STT_6_interleave_sttbuild":   "STT_6_interleave",
    "STT_all_recon":               "STT_all",
    "STT_all_sttbuild":            "STT_all",
    "STT_all_amulet":              "STT_all",
    "Recon_6":                     "Recon_6",
}

CATS = ["SLF", "LL", "OtherLoad", "BR", "Other"]

_VARIANT_RE = re.compile(r"_v[0-9]+$")
def base_stem(s: str) -> str:
    return _VARIANT_RE.sub("", s)


def find_window_results(run_dir: Path):
    """Yield (mode_label, window_results_path) for a run dir."""
    for mode_dir in sorted(run_dir.iterdir()):
        if not mode_dir.is_dir():
            continue
        wr = mode_dir / "window-results.json"
        if wr.exists():
            yield mode_dir.name, wr


def categorize_one(stem: str, xml_dir: Path) -> str:
    p = xml_dir / (stem + ".xml")
    if not p.exists():
        return "MissingXML"
    try:
        d = parse_xml(p)
        if d is None:
            return "ParseErr"
        return categorize(d)
    except Exception:
        return "Err"


def analyze_run(run_dir: Path, xml_dir: Path, candidates_only: bool = False):
    run_label = run_dir.name
    if not xml_dir.exists():
        print(f"  [skip] {run_label}: xml_dir missing: {xml_dir}")
        return

    print(f"\n=== {run_label}  (xml={xml_dir.name}) ===")
    for mode, wr_path in find_window_results(run_dir):
        with wr_path.open() as fh:
            recs = json.load(fh)
        hits = [r for r in recs if r.get("issued_in_window")]
        total = len(recs)
        if not hits:
            print(f"  {mode:25s}  recs={total:<7} hits=0")
            continue

        cat_count   = Counter()
        cat_full    = Counter()       # triggered == gridsize
        cat_partial = Counter()       # 0 < triggered < gridsize
        examples    = defaultdict(list)

        for r in hits:
            stem = base_stem(r["name"])
            cat = categorize_one(stem, xml_dir)
            cat_count[cat] += 1
            gs = r.get("sweep_grid_size", 0)
            tg = r.get("sweep_triggered", 0)
            if gs and tg == gs:
                cat_full[cat] += 1
            elif 0 < tg < gs:
                cat_partial[cat] += 1
            if len(examples[cat]) < 5:
                examples[cat].append(r["name"])

        cats_str = ", ".join(
            f"{c}={cat_count[c]}" for c in CATS + ["MissingXML"]
            if cat_count.get(c)
        )
        print(f"  {mode:25s}  recs={total:<7} hits={len(hits):<6}  {cats_str}")
        for c in CATS:
            n = cat_count.get(c, 0)
            if not n: continue
            if candidates_only and c == "BR":
                continue
            f = cat_full.get(c, 0); p = cat_partial.get(c, 0)
            ex = ", ".join(examples[c][:3])
            more = f" (+{n-3} more)" if n > 3 else ""
            print(f"      {c:<10} n={n:<5}  full={f:<5}  partial={p:<5}  e.g. {ex}{more}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append",
                    help="Limit to one or more run dirs (repeatable)")
    ap.add_argument("--candidates-only", action="store_true",
                    help="Hide BR category (skip presumed-bogus xorq hits)")
    ap.add_argument("--results-root", default=str(ROOT / "results"))
    ap.add_argument("--testsets-root", default=str(ROOT / "testsets"))
    args = ap.parse_args()

    results_root = Path(args.results_root)
    testsets_root = Path(args.testsets_root)

    runs = []
    for d in sorted(results_root.iterdir()):
        if not d.is_dir(): continue
        if d.name.startswith("_"): continue
        if args.run and d.name not in args.run: continue
        runs.append(d)

    for run_dir in runs:
        testset = TESTSET_OVERRIDES.get(run_dir.name, run_dir.name)
        xml_dir = testsets_root / testset / "xml"
        # Recon_6 layout has its own results dir convention
        analyze_run(run_dir, xml_dir, candidates_only=args.candidates_only)


if __name__ == "__main__":
    main()
