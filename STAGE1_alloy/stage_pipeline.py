#!/usr/bin/env python3
"""stage_pipeline.py — staged Alloy enumeration (stage1 cores -> stage2 flesh-out).

Two-stage XML producer that replaces the flat `pipeline.py xml` phase for a model:

  STAGE 1  enumerate MAXIMALLY-MINIMIZED leak cores from a core model
           (default STT_6_core.als: idx/length restrictions removed, all
           perturbation-minimality RO+RI+RC+RR+RS on). Few small cores.
  SEED     translate each core into a structural Alloy seed predicate
           (stage_seed.build_pred) pinning its leak shape.
  STAGE 2  for EACH core, seed it into the real STT_6.als and enumerate up to
           --per-core fleshed-out instances (STT_6 adds extra instructions /
           operands up to its `exactly 6` bound; no RI/RO minimality there).

This balances coverage: instead of letting one base instance dominate the cap,
each minimal core contributes at most --per-core fleshed-out tests. Output XMLs
are globally renumbered into <out-xml-dir> so the unchanged llvm/asm/gem5 phases
consume them exactly like a flat testset's xml/.

Example:
  python3 stage_pipeline.py \
      --core-model models/STT_6_core.als --flesh-model models/STT_6.als \
      --out-xml-dir ../testsets/STT_6_staged/xml \
      --max-cores 200 --per-core 50
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))
import stage_seed  # noqa: E402

ALLOY_CP = "alloy6.jar:."
DRIVER = "a6CountModels"


def run_alloy(model_path, out_dir, limit, timeout=None):
    """Run the Alloy enumerator. a6CountModels writes each instance to disk as it
    is found, so a wall-clock timeout (exhaustion proofs can be very slow) simply
    bounds the search and keeps whatever was already enumerated."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["java", "-cp", ALLOY_CP, DRIVER, str(model_path), str(out_dir), str(limit)]
    if timeout:
        cmd = ["timeout", str(timeout)] + cmd
    print(f"  $ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode == 124:
        print(f"  (timed out after {timeout}s — keeping instances found so far)", flush=True)
    elif r.returncode != 0:
        print(f"  (alloy exited {r.returncode})", flush=True)
    return sorted(out_dir.glob("inst-*.txt"))


def build_seeded_model(flesh_model_text, seed_pred_text):
    """Conjoin seed_core into STT_6's gen_lit run, append the seed predicate."""
    needle = "run gen_lit {\n  gen_useful_litmus\n}"
    if needle not in flesh_model_text:
        sys.exit("could not find `run gen_lit { gen_useful_litmus }` in flesh model")
    swapped = flesh_model_text.replace(
        needle, "run gen_lit {\n  gen_useful_litmus\n  seed_core\n}")
    return swapped + "\n\n" + seed_pred_text + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core-model", default="models/STT_6_core.als")
    ap.add_argument("--flesh-model", default="models/STT_6.als")
    ap.add_argument("--out-xml-dir", required=True)
    ap.add_argument("--max-cores", type=int, default=1000,
                    help="cap on stage-1 cores enumerated")
    ap.add_argument("--per-core", type=int, default=50,
                    help="cap on fleshed-out instances per core (stage 2)")
    ap.add_argument("--core-timeout", type=int, default=120,
                    help="wall-clock seconds for stage-1 core enumeration "
                         "(exhaustion proofs are slow; keeps cores found so far)")
    ap.add_argument("--flesh-timeout", type=int, default=180,
                    help="wall-clock seconds per stage-2 seeded enumeration")
    ap.add_argument("--keep-work", action="store_true",
                    help="keep the scratch dir of per-core seeded models")
    args = ap.parse_args()

    core_model = (HERE / args.core_model).resolve()
    flesh_model = (HERE / args.flesh_model).resolve()
    flesh_text = flesh_model.read_text()
    out_xml = Path(args.out_xml_dir).resolve()
    out_xml.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="stage_pipeline_"))
    print(f"[stage1] enumerating cores from {core_model.name} (limit {args.max_cores})")
    core_dir = work / "cores"
    cores = run_alloy(core_model, core_dir, args.max_cores, timeout=args.core_timeout)
    print(f"[stage1] {len(cores)} core(s)")

    global_n = 0
    manifest = []
    for ci, core_txt in enumerate(cores):
        rels = stage_seed.parse_txt(str(core_txt))
        seed_pred = stage_seed.build_pred(rels, "seed_core")
        seeded_path = work / f"seeded_{ci:04d}.als"
        seeded_path.write_text(build_seeded_model(flesh_text, seed_pred))

        ext_dir = work / f"ext_{ci:04d}"
        print(f"[stage2] core {ci} ({core_txt.name}) -> flesh-out (limit {args.per_core})")
        run_alloy(seeded_path, ext_dir, args.per_core, timeout=args.flesh_timeout)
        exts = sorted(ext_dir.glob("inst-*.xml"))
        for x in exts:
            global_n += 1
            dst = out_xml / f"inst-{global_n:06d}.xml"
            shutil.copy(x, dst)
            txt = x.with_suffix(".txt")
            if txt.exists():
                shutil.copy(txt, dst.with_suffix(".txt"))
        manifest.append(f"core {ci:04d} {core_txt.name}: {len(exts)} fleshed -> "
                        f"inst-{global_n-len(exts)+1:06d}..inst-{global_n:06d}")
        print(f"  -> {len(exts)} fleshed-out instances")

    (out_xml / "_staged_manifest.txt").write_text(
        f"core-model={core_model.name} flesh-model={flesh_model.name} "
        f"max_cores={args.max_cores} per_core={args.per_core}\n"
        f"cores={len(cores)} total_instances={global_n}\n\n" + "\n".join(manifest) + "\n")
    print(f"[done] {len(cores)} cores -> {global_n} instances in {out_xml}")
    print(f"       manifest: {out_xml/'_staged_manifest.txt'}")
    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print(f"       scratch kept: {work}")


if __name__ == "__main__":
    main()
