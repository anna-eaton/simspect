#!/usr/bin/env python3
"""
bucket_hits.py — fixed-harness version (2026-11-07) of the per-results "big test":
run every diagnostic in this folder against every hit and bucket each hit by the
FIRST cause that matches, leaving only unexplained hits as NEW candidates.

Same protocol and auto-discovery as results/SPT_6_oneLP_fence__latest/diagnostics/
bucket_hits.py (disqualifiers, then real_bug, then NEW), with two additions:
  * every transmitter kind with a window-results.json (ld, br_x, other_x), not
    only ld. A diagnostic declares the kinds it judges with KINDS (default
    ("ld",), so the older ld-only diagnostics keep their meaning);
  * a diagnostic whose evidence differs per branch mode exposes MODE; it is set
    to the mode before is_known is called.
Canonical source: STAGE3_gem5/triage/diag/ in the repo.

Usage:  python3 bucket_hits.py --xml-dir <testset>/xml
"""
import argparse, json, importlib.util, sys, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_DIR = HERE.parent
_PHASE_RANK = {"disqualifier": 0, "real_bug": 1}


def _discover():
    diags = []
    for p in sorted(HERE.glob("diag_*.py")):
        spec = importlib.util.spec_from_file_location(p.stem, p)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"  ! skip {p.name}: import error {e}", file=sys.stderr)
            continue
        if not hasattr(mod, "is_known"):
            continue
        diags.append(dict(name=p.stem.replace("diag_", ""), mod=mod,
                          phase=getattr(mod, "PHASE", "real_bug"), needs_gem5=getattr(mod, "NEEDS_GEM5", False),
                          order=getattr(mod, "ORDER", 100), kinds=tuple(getattr(mod, "KINDS", ("ld",)))))
    diags.sort(key=lambda d: (_PHASE_RANK.get(d["phase"], 9), d["order"]))
    return diags


def _cache_setup_of(window_json):
    """stem -> cache_setup the test actually ran with (2026-11-09). From the record
    (pipeline.py keeps it on non-warm runs; `random` differs per test), else from the
    campaign manifest when it names one fixed strategy, else "unknown"."""
    try:
        man = json.loads((RUN_DIR / "manifest.json").read_text()).get("cache_setup", "warm")
    except (OSError, ValueError):
        man = "warm"
    fallback = man if man != "random" else "unknown"
    data = json.loads(Path(window_json).read_text())
    recs = data if isinstance(data, list) else (data.get("results") or list(data.values()))
    return {r["name"].split("__")[0]: r.get("cache_setup", fallback)
            for r in recs if isinstance(r, dict)}


def _hits(window_json):
    data = json.loads(Path(window_json).read_text())
    recs = data if isinstance(data, list) else (data.get("results") or list(data.values()))
    return sorted({r["name"].split("__")[0] for r in recs if isinstance(r, dict) and r.get("issued_in_window")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml-dir", type=Path, required=True)
    ap.add_argument("--with-gem5", action="store_true")
    a = ap.parse_args()
    diags = _discover()
    print("Diagnostics (in apply order):")
    for d in diags:
        print(f"  {d['phase']:12} order={d['order']:<4} kinds={','.join(d['kinds']):12} {d['name']}"
              + (" [gem5]" if d["needs_gem5"] else ""))
    active = [d for d in diags if a.with_gem5 or not d["needs_gem5"]]
    out = HERE / "buckets"; out.mkdir(exist_ok=True)
    summary = {}
    for wr in sorted(RUN_DIR.glob("mispredict_*/*/window-results.json")):
        mode, kind = wr.parts[-3], wr.parts[-2]
        stems = _hits(wr)
        if not stems:
            continue
        use = [d for d in active if kind in d["kinds"]]
        buckets = collections.OrderedDict((d["name"], []) for d in use)
        buckets["NEW_candidate_pure_bug"] = []
        reasons = {}
        for s in stems:
            for d in use:
                if hasattr(d["mod"], "MODE"):
                    d["mod"].MODE = mode
                m, why = d["mod"].is_known(s, a.xml_dir)
                if m:
                    buckets[d["name"]].append(s); reasons[s] = f"{d['name']}: {why}"; break
            else:
                buckets["NEW_candidate_pure_bug"].append(s)
        md = out / mode / kind; md.mkdir(parents=True, exist_ok=True)
        print(f"\n== {mode}/{kind}  ({len(stems)} hit tests) ==")
        for b, lst in buckets.items():
            (md / f"{b}.txt").write_text("".join(f"{x}\t{reasons.get(x, '')}\n" for x in lst))
            print(f"   {b:34} {len(lst)}" + ("  <-- review" if b.startswith("NEW") and lst else ""))
        summary[f"{mode}/{kind}"] = {b: len(l) for b, l in buckets.items()}
        cs_of = _cache_setup_of(wr)
        split = {}
        for b, lst in buckets.items():
            for x in lst:
                c = cs_of.get(x, "unknown")
                split.setdefault(c, {}).setdefault(b, 0)
                split[c][b] += 1
        if set(split) - {"warm"}:          # only when some test did not run warm
            summary[f"{mode}/{kind}"]["by_cache_setup"] = split
            print("   by cache_setup: " + "; ".join(
                f"{c}: " + ", ".join(f"{b}={n}" for b, n in d.items()) for c, d in sorted(split.items())))
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nwrote buckets under {out}/<mode>/<kind>/")


if __name__ == "__main__":
    main()
