#!/usr/bin/env python3
"""
diag_stt_vp_squash_race.py — bucket a check_ld ld hit as the STT visibility-point /
squash-drain race (see stt_vp_squash_race.md, same dir).

ONE cause, conservative. Re-runs gem5 under the hit's own run_config and checks the
mechanistic signature of the race:

  (1) the xmit load makes a REAL cache access  — "successfully sent out packet(s)"
      (reuses diag_ld_cache_reach: fate == reached_cache; not a delay/spec-read/
      never-exec check_ld false positive), AND
  (2) the xmit load is SQUASHED (wrong-path, not retired), AND
  (3) the cache packet goes out at/after the controlling MISPREDICT branch's
      resolution (its Commit mispredict-squash broadcast) — i.e. the taint was
      cleared by the branch resolving (isPrevBrsResolved) and the load slipped its
      access into the resolution→squash gap.

Verdicts:
  stt_vp_squash_race   — signature (1)+(2)+(3): attributed to THIS bug.
  stt_no_hold          — real access BEFORE the branch resolved (STT never held it):
                         a DIFFERENT/stronger anomaly → left as NEW, not bucketed here.
  committed_access     — real access but the load RETIRED (architectural, not spec).
  not_real_access      — no real cache packet (cache-reach FP) → not this bug.
  no_mispredict_branch — annotation has no mispredict branch → n/a.

Only `stt_vp_squash_race` is treated as explained/known. Everything else stays NEW
(conservative — never hide a possible real/leak we don't fully understand).

  python3 diag_stt_vp_squash_race.py <dir-with-.s+.ann.json> \
      --config ../STT_6/run_config.jsonc \
      --hits-from ../sample/mispredict_not_taken/window-results.json \
      --jobs 12 --out race.json
"""
import argparse, json, os, re, sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]                       # results/experiments/slow_comm_squash1/diagnostics → repo
STAGE3 = REPO / "STAGE3_gem5"


def _apply_config_env(config_path: Path):
    sys.path.insert(0, str(REPO)); import pipeline
    cfg = pipeline.load_config(config_path)
    env = pipeline._build_gem5_env(cfg.get("gem5", {}), cfg.get("speculation", {}))
    os.environ.update({k: str(v) for k, v in env.items()})
    sc = cfg.get("gem5", {}).get("scheme")
    if sc is not None:
        os.environ["SIMSPECT_SCHEME"] = str(sc)


_MISPREDICT = ("mispredict_not_taken", "mispredict_taken")


def diagnose_one(args):
    s_path, ann_path = args
    sys.path.insert(0, str(STAGE3))
    import gem5_common as gc
    from diag_ld_cache_reach import classify_trace
    if "SIMSPECT_SCHEME" in os.environ:
        gc._scheme = int(os.environ["SIMSPECT_SCHEME"])
    import tempfile, shutil
    name = s_path.stem
    wd = Path(tempfile.mkdtemp(prefix=f"race_{name}_"))
    rec = dict(name=name, verdict=None, error=None)
    try:
        parts = gc.load_annotation(ann_path)
        ann_full = json.loads(Path(ann_path).read_text())
        binary = gc.build_binary(s_path, wd)
        xmit_pc = gc.resolve_pc(binary, name, parts["xmit"])
        fnc_pc = gc.resolve_pc(binary, name, parts["fnc"])
        # mispredict branch PCs (absolute addr in the ann; runs use base 0x401020)
        br_pcs = [int(e["branch_addr"]) for e in ann_full.get("annotations", [])
                  if e.get("mode") in _MISPREDICT and e.get("branch_addr") is not None]
        if xmit_pc is None:
            rec["verdict"] = "no_xmit_pc"; return rec
        if not br_pcs:
            rec["verdict"] = "no_mispredict_branch"; return rec
        trace = gc.run_gem5(binary, wd, ann_path=ann_path, fnc_pc=fnc_pc)
        cr = classify_trace(trace, xmit_pc)
        rec.update(fate=cr["fate"], packet_tick=cr.get("packet_tick"),
                   load_squash_tick=cr.get("squash_tick"))
        squashes = gc.parse_commit_squashes(trace)        # branch_pc -> [resolution ticks]
        br_resolve = min((t for pc in br_pcs for t in squashes.get(pc, [])), default=None)
        rec["branch_resolve_tick"] = br_resolve
        rec["mispredict_branch_pcs"] = [hex(p) for p in br_pcs]

        if cr["fate"] != "reached_cache":
            rec["verdict"] = "not_real_access"
        elif cr.get("squash_tick") is None:
            rec["verdict"] = "committed_access"        # accessed + retired (not squashed)
        elif br_resolve is None:
            rec["verdict"] = "stt_no_hold"             # accessed, no branch resolution seen
        elif cr["packet_tick"] >= br_resolve:
            rec["verdict"] = "stt_vp_squash_race"      # the bug: access at/after resolution, pre-squash
        else:
            rec["verdict"] = "stt_no_hold"             # accessed BEFORE resolution (never held)
    except Exception as e:
        rec["verdict"] = "error"; rec["error"] = str(e)[-300:]
    finally:
        shutil.rmtree(wd, ignore_errors=True)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--hits-from", type=Path, action="append", required=True)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    _apply_config_env(args.config)
    stems = set()
    for hf in args.hits_from:
        stems |= {r["name"] for r in json.loads(hf.read_text())
                  if r.get("issued_in_window") is True}

    pairs = []
    for s in sorted(args.input_dir.glob("*.s")):
        if s.stem not in stems:
            continue
        ann = args.input_dir / (s.stem + ".ann.json")
        if ann.exists():
            pairs.append((s.resolve(), ann.resolve()))

    print(f"diagnosing {len(pairs)} hit(s) for STT vp/squash race  jobs={args.jobs}",
          file=sys.stderr)
    results = []
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            for fu in as_completed([ex.submit(diagnose_one, p) for p in pairs]):
                results.append(fu.result())
    else:
        results = [diagnose_one(p) for p in pairs]

    v = Counter(r["verdict"] for r in results)
    attributed = v.get("stt_vp_squash_race", 0)
    print(f"\nverdicts: {dict(v)}", file=sys.stderr)
    print(f"ATTRIBUTED to STT vp/squash race (KNOWN): {attributed} / {len(results)}; "
          f"rest stay NEW/other", file=sys.stderr)
    if args.out:
        args.out.write_text(json.dumps(results, indent=2))
        print(f"written: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
