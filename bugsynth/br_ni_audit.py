#!/usr/bin/env python3
"""br_ni_audit.py — non-interference br_x AUDIT PASS that emits the window-results.json schema.

This is item #1 (pipeline integration) in the form that does NOT touch mainline: a SEPARATE consumer
(like results/_sweep_watcher.py / testrun.py), not an edit to pipeline.py's per-test _KIND_TO_CHECKER.
Rationale: the NI verdict needs 5 gem5 runs/gadget (value-flip × {scheme0 control, scheme2} + self-check),
so folding it into every per-test sweep would 5× the gem5 cost of all br_x tests. An audit pass keeps the
fast `check_br.py` for routine sweeps and runs the rigorous NI audit on demand, while still producing the
standard `window-results.json` rows so the existing results/diagnostics tooling consumes it unchanged.

It imports `check_br_ni.audit_gadget` (one verdict per br_x gadget across a stall band) and writes, per
mode, a `window-results.json` where:
    issued_in_window = (verdict == "LEAK")        # a real, taint-gated branch leak under STT
    status           = "leak" | "safe" | "vacuous"
plus an `ni_audit.json` with the full per-gadget detail (live_stall, pub/any moves, self_ok) and a manifest
(build/scheme/stalls). VACUOUS rows are written with issued_in_window=false and flagged so they're excluded
from the leak/sound score (no public observable forms at any stall — uninformative, not a pass/fail).

Usage:
  python3 bugsynth/br_ni_audit.py --model STT_6 [--mode mispredict_not_taken] [--sweep] [--out-name NAME]
"""
import os, sys, json, argparse, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import check_br_ni as ni


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="STT_6")
    ap.add_argument("--testset", default=None)
    ap.add_argument("--mode", default="mispredict_not_taken")
    ap.add_argument("--stall", type=int, default=2000)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--stalls", default=None)
    ap.add_argument("-n", type=int, default=0)
    ap.add_argument("--out-name", default=None, help="results dir name (default = <model>_ni)")
    a = ap.parse_args()
    base = ROOT / f"testsets/{a.testset or a.model}/{a.mode}"
    stalls = ([int(x) for x in a.stalls.split(",")] if a.stalls
              else [500, 2000, 2500, 5000] if a.sweep else [a.stall])
    stems = ni.list_brx_stems(base)
    if a.n: stems = stems[:a.n]

    out_dir = ROOT / "results" / (a.out_name or f"{a.model}_ni") / a.mode
    out_dir.mkdir(parents=True, exist_ok=True)
    window, detail = [], []
    sound = leak = vac = err = 0
    for stem in stems:
        try:
            r = ni.audit_gadget(base, stem, stalls)
        except Exception as e:
            err += 1
            detail.append(dict(stem=stem, verdict="ERROR", error=f"{type(e).__name__}: {str(e)[:80]}"))
            print(f"{stem}: ERROR {type(e).__name__}: {str(e)[:60]}")
            continue
        v = r["verdict"]
        status = {"LEAK": "leak", "SOUND": "safe", "VACUOUS": "vacuous"}[v]
        window.append(dict(name=stem, status=status, issued_in_window=(v == "LEAK"),
                           vacuous=(v == "VACUOUS")))
        detail.append(r)
        sound += v == "SOUND"; leak += v == "LEAK"; vac += v == "VACUOUS"
        print(f"{stem}: {v:7s} live_stall={r['live_stall']} pub_moves={int(r['pub_moves'])} "
              f"old_check_br={int(r['any_moves'])} self={'ok' if r['self_ok'] else 'NO!'}")

    (out_dir / "window-results.json").write_text(json.dumps(window, indent=1))
    (out_dir / "ni_audit.json").write_text(json.dumps(detail, indent=1))
    manifest = dict(tool="br_ni_audit", model=a.model, testset=str(a.testset or a.model), mode=a.mode,
                    stalls=stalls, gem5="/work/stt/build/X86/gem5.opt", scheme=2,
                    secret_param="value-flip", liveness="scheme-0 positive control",
                    counts=dict(sound=sound, leak=leak, vacuous=vac, err=err),
                    when=datetime.datetime.now().isoformat(timespec="seconds"))
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    tot = sound + leak
    print(f"\n# {sound}/{tot} LIVE SOUND, {leak}/{tot} LEAK  ({vac} vacuous, {err} err)")
    print(f"# wrote {out_dir}/window-results.json (+ ni_audit.json, manifest.json)")


if __name__ == "__main__":
    main()
