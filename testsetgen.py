#!/usr/bin/env python3
"""
testsetgen.py — SimSpect test-set generator (the PRODUCER half of the pipeline).

Pipelines the three generation stages so they run CONCURRENTLY: Alloy keeps
enumerating XML in the background while the llvm (parsexml) and asm+annotation
stages consume each instance the moment it lands on disk. Contrast with
`pipeline.py all`, a strictly sequential for-loop that blocks inside the XML
phase until all instances exist before llvm even starts — here you see all
three stages make progress at once.

Purely a producer: NO gem5, NO build target. The resulting
testsets/<model>/<mode>/{asm,ann} are consumed by testrun.py (the executor).

Reuses pipeline.py's phase functions unchanged (imported, not copied), so the
generation logic is identical to the battle-tested pipeline — this script only
adds the concurrency + a fuller provenance snapshot.

Resumable: llvm/asm skip any instance whose output already exists (same per-stem
skip pipeline.py uses), so a killed run resumes cleanly. The XML phase is the
one exception — Alloy can't resume mid-enumeration; a killed `xml` restarts
from instance 0.

Usage:
    python3 testsetgen.py --model SPT_6_oneLP --config run_config_SPT_6_oneLP.jsonc
                          [--interval 15] [--force]
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path

from pipeline import ROOT, load_config, resolve, phase_xml, phase_llvm, phase_asm


def _count(p: Path, pat: str) -> int:
    return sum(1 for _ in p.glob(pat)) if p.is_dir() else 0


def write_provenance(cfg: dict, model: str, testset_base: Path,
                     config_path: Path) -> None:
    """Self-describing snapshot: every Stage-2 source, the instruction tables,
    the Alloy model, the resolved config, plus a manifest (git SHA, alloy-jar
    identity, timestamp). Written fresh at each producer launch."""
    stage2 = resolve(cfg["paths"]["stage2_dir"])
    tables = resolve(cfg["paths"]["instruction_tables"])
    model_file = resolve(cfg["paths"]["models_dir"]) / f"{model}.als"
    alloy_jar = resolve(cfg["paths"]["alloy_stage"]) / "alloy6.jar"

    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT),
            text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        git_sha = "unknown"

    manifest = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": model,
        "git_sha": git_sha,
        "config": config_path.name,
        "alloy_jar": {
            "path": str(alloy_jar),
            "size": alloy_jar.stat().st_size if alloy_jar.exists() else None,
            "mtime": alloy_jar.stat().st_mtime if alloy_jar.exists() else None,
        },
    }

    sources = [
        (stage2 / "parsexml.py",         "parsexml.py"),
        (stage2 / "compile_annotate.py", "compile_annotate.py"),
        (stage2 / "batch_generate.py",   "batch_generate.py"),
        (tables,                         f"instruction_tables/{tables.name}"),
        (model_file,                     model_file.name),
        (config_path,                    config_path.name),
    ]

    testset_base.mkdir(parents=True, exist_ok=True)
    man_path = testset_base / "_provenance_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2))
    out = testset_base / "provenance.tar.gz"
    with tarfile.open(out, "w:gz") as tf:
        tf.add(man_path, arcname="manifest.json")
        for src, arc in sources:
            if src.exists():
                tf.add(src, arcname=arc)
    man_path.unlink(missing_ok=True)
    present = [arc for src, arc in sources if src.exists()]
    print(f"[provenance] {out}  (git {git_sha[:8]}; {len(present)} sources)",
          flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--config", default="run_config.jsonc")
    ap.add_argument("--interval", type=int, default=15,
                    help="seconds between llvm/asm drain passes when caught up")
    ap.add_argument("--force", action="store_true",
                    help="re-enumerate XML and regenerate every stage")
    ap.add_argument("--follow", action="store_true",
                    help="attach to XML being enumerated by ANOTHER process: "
                         "skip the xml phase, stream llvm/asm over the growing "
                         "xml/ dir, and loop forever until killed (never "
                         "auto-terminate). Touches nothing the xml producer owns.")
    a = ap.parse_args()

    config_path = (ROOT / a.config if not Path(a.config).is_absolute()
                   else Path(a.config))
    if not config_path.exists():
        sys.exit(f"error: config not found: {config_path}")
    cfg = load_config(config_path)

    testset_dir = resolve(cfg["paths"].get("testset_dir", "testsets"))
    testset_base = testset_dir / a.model
    testset_base.mkdir(parents=True, exist_ok=True)
    # In --follow mode another process owns the xml/ dir (and already wrote a
    # provenance snapshot); don't touch it.
    if not a.follow:
        write_provenance(cfg, a.model, testset_base, config_path)

    modes = cfg.get("speculation", {}).get("branch_modes", [])
    mode_list = modes if modes else [None]
    xml_dir = testset_base / "xml"
    cap = int(cfg.get("alloy", {}).get("max_instances", 0))

    def _mode_base(m):
        return (testset_base / m) if m else testset_base

    # ── Stage 1 (xml): run Alloy in the background unless --follow, in which
    #    case another process is enumerating and we only consume its output. ──
    xml_done = threading.Event()

    def _xml():
        try:
            phase_xml(cfg, a.model, testset_base, a.force)
        except SystemExit as e:
            print(f"[gen] xml phase exited: {e}", flush=True)
        finally:
            xml_done.set()

    if not a.follow:
        threading.Thread(target=_xml, daemon=True).start()

    def _drain() -> int:
        """One llvm+asm pass over all currently-available work (per-stem skip
        makes it incremental). Returns the total asm count across modes."""
        for m in mode_list:
            mb = _mode_base(m)
            mb.mkdir(parents=True, exist_ok=True)
            if _count(xml_dir, "inst-*.xml") == 0:
                continue
            # phase_llvm needs xml; phase_asm needs llvm — both sys.exit on an
            # empty input dir, so guard before each call and swallow a transient
            # SystemExit (e.g. a half-written XML) to retry next pass.
            try:
                phase_llvm(cfg, a.model, mb, False, mode=m,
                           xml_dir_override=xml_dir)
            except SystemExit as e:
                print(f"[gen] llvm({m}) skipped this pass: {e}", flush=True)
            if _count(mb / "llvm", "*.ll") > 0:
                try:
                    phase_asm(cfg, a.model, mb, False)
                except SystemExit as e:
                    print(f"[gen] asm({m}) skipped this pass: {e}", flush=True)
        return sum(_count(_mode_base(m) / "asm", "inst-*.s") for m in mode_list)

    prev_asm = -1
    while True:
        asm_total = _drain()
        xml_n = _count(xml_dir, "inst-*.xml")
        per = "  ".join(
            f"[{m or 'flat'}] llvm {_count(_mode_base(m) / 'llvm', '*.ll')} "
            f"asm {_count(_mode_base(m) / 'asm', 'inst-*.s')} "
            f"ann {_count(_mode_base(m) / 'ann', '*.ann.json')}"
            for m in mode_list)
        state = ("following" if a.follow
                 else "done" if xml_done.is_set() else "enumerating")
        print(f"[gen {time.strftime('%H:%M:%S')}] xml {xml_n}"
              f"{'/' + str(cap) if cap else ''} ({state})  |  {per}", flush=True)

        # --follow never auto-terminates (the external producer decides when
        # xml is done; kill this process manually). Otherwise stop once Alloy
        # has finished and a full pass produced no new asm.
        if not a.follow and xml_done.is_set() and asm_total == prev_asm:
            print("[gen] complete — xml done and no new asm produced. "
                  "Testset ready for testrun.py.", flush=True)
            break
        prev_asm = asm_total
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
