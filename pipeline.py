#!/usr/bin/env python3
"""
pipeline.py — SimSpect top-level pipeline orchestrator.

Reads run_config.jsonc and drives the four pipeline phases for a given
Alloy model stem.  Each phase is idempotent: if its output directory is
already populated the phase is skipped unless --force is passed.

Usage:
    python3 pipeline.py <phase> --model <stem> [--config run_config.jsonc] [--force]

Phases:
    xml     Phase 1 — Alloy model → inst-*.xml instances
    llvm    Phase 2 — inst-*.xml  → inst-*.ll + bare inst-*.ann.json
    asm     Phase 3 — inst-*.ll   → inst-*.s / *.o + resolved inst-*.ann.json
    gem5    Phase 4 — gem5 O3PipeView simulation + speculative window check
    all     Run phases 1-4 in sequence
    clean   Delete generated/<model>/ entirely

Output layout (under generated/<model>/):
    xml/        inst-*.xml, inst-*.txt
    llvm/       inst-*.ll  (+ bare inst-*.ann.json written by batch_generate)
    asm/        inst-*.s, inst-*.o
    ann/        inst-*.ann.json  (with resolved x86 offsets, from compile_annotate)
    results/    window-results.json, window-hits.txt, batch_NNNN_results.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()


# ── Config helpers ────────────────────────────────────────────────────────────

def load_config(path: Path) -> dict:
    """Load a JSON file that may contain // line comments and /* block comments */."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'//[^\n]*',  '', text)
    return json.loads(text)


def resolve(cfg_value: str) -> Path:
    """Resolve a config path: absolute → as-is; relative → relative to ROOT."""
    p = Path(cfg_value)
    return p if p.is_absolute() else (ROOT / p).resolve()


# ── Phase 1: Alloy → XML ──────────────────────────────────────────────────────

def phase_xml(cfg: dict, model: str, out_base: Path, force: bool) -> None:
    xml_dir = out_base / "xml"
    if not force and xml_dir.exists() and any(xml_dir.glob("inst-*.xml")):
        n = sum(1 for _ in xml_dir.glob("inst-*.xml"))
        print(f"[xml] {xml_dir.name}/ already has {n} instances — skipping "
              f"(pass --force to re-enumerate)")
        return

    xml_dir.mkdir(parents=True, exist_ok=True)

    alloy_stage = resolve(cfg["paths"]["alloy_stage"])
    model_file  = resolve(cfg["paths"]["models_dir"]) / f"{model}.als"
    if not model_file.exists():
        sys.exit(f"error: model file not found: {model_file}")

    max_inst = cfg.get("alloy", {}).get("max_instances", 100000)

    cmd = [
        "java", "-cp", "alloy6.jar:.", "a6CountModels",
        str(model_file), str(xml_dir), str(max_inst),
    ]
    print(f"[xml] Enumerating instances from {model_file.name} (cap={max_inst}) …")
    result = subprocess.run(cmd, cwd=str(alloy_stage),
                            capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(f"error: a6CountModels failed (exit {result.returncode})")

    count = sum(1 for _ in xml_dir.glob("inst-*.xml"))
    print(f"[xml] Done — {count} instances")


# ── Phase 2: XML → LLVM IR ────────────────────────────────────────────────────

def phase_llvm(cfg: dict, model: str, out_base: Path, force: bool) -> None:
    xml_dir  = out_base / "xml"
    llvm_dir = out_base / "llvm"

    xml_files = sorted(xml_dir.glob("inst-*.xml")) if xml_dir.exists() else []
    if not xml_files:
        sys.exit("error: generated/<model>/xml/ is empty — run the 'xml' phase first")

    llvm_dir.mkdir(parents=True, exist_ok=True)

    stage2       = resolve(cfg["paths"]["stage2_dir"])
    tables_path  = resolve(cfg["paths"]["instruction_tables"])

    if force:
        todo = xml_files
    else:
        todo = [f for f in xml_files if not (llvm_dir / (f.stem + ".ll")).exists()]

    if not todo:
        done = sum(1 for f in xml_files if (llvm_dir / (f.stem + ".ll")).exists())
        print(f"[llvm] All {done} .ll files already generated — skipping")
        return

    print(f"[llvm] Generating LLVM IR for {len(todo)}/{len(xml_files)} instances …")

    # batch_generate expects all XMLs in one directory; use a temp dir for the
    # subset we actually need so it doesn't regenerate already-done files.
    with tempfile.TemporaryDirectory(prefix="simspect_xml_") as tmp:
        tmp_path = Path(tmp)
        for f in todo:
            shutil.copy(f, tmp_path / f.name)

        cmd = [
            sys.executable,
            str(stage2 / "batch_generate.py"),
            str(tmp_path),
            "--out", str(llvm_dir),
            "--kind",
            "--instruction-tables", str(tables_path),
        ]
        result = subprocess.run(cmd, cwd=str(stage2),
                                capture_output=True, text=True)
        # Print only error/skip lines from batch_generate
        for line in result.stdout.splitlines():
            if "[err]" in line or "[skip]" in line:
                print(f"  {line.strip()}")
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            sys.exit(f"error: batch_generate.py failed (exit {result.returncode})")

    done = sum(1 for f in xml_files if (llvm_dir / (f.stem + ".ll")).exists())
    failed = len(xml_files) - done
    msg = f"[llvm] Done — {done}/{len(xml_files)} .ll files"
    if failed:
        msg += f"  ({failed} failed)"
    print(msg)


# ── Phase 3: LLVM IR → x86 asm + resolved annotations ───────────────────────

def phase_asm(cfg: dict, model: str, out_base: Path, force: bool) -> None:
    llvm_dir = out_base / "llvm"
    asm_dir  = out_base / "asm"
    ann_dir  = out_base / "ann"

    ll_files = sorted(llvm_dir.glob("*.ll")) if llvm_dir.exists() else []
    if not ll_files:
        sys.exit("error: generated/<model>/llvm/ is empty — run the 'llvm' phase first")

    asm_dir.mkdir(parents=True, exist_ok=True)
    ann_dir.mkdir(parents=True, exist_ok=True)

    stage2 = resolve(cfg["paths"]["stage2_dir"])

    if force:
        todo = ll_files
    else:
        todo = [f for f in ll_files if not (asm_dir / (f.stem + ".s")).exists()]

    if not todo:
        done = sum(1 for f in ll_files if (asm_dir / (f.stem + ".s")).exists())
        print(f"[asm] All {done} .s files already compiled — skipping")
        return

    print(f"[asm] Compiling {len(todo)}/{len(ll_files)} .ll files …")
    ok = err = 0

    for ll in todo:
        r = subprocess.run(
            [
                sys.executable,
                str(stage2 / "compile_annotate.py"),
                str(ll),
                "--out-dir", str(asm_dir),
                "--ann-dir", str(ann_dir),
            ],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            ok += 1
        else:
            err += 1
            print(f"  [err] {ll.name}: {r.stderr.strip()[:200]}")
        done_count = ok + err
        if done_count % 500 == 0:
            print(f"  progress: {done_count}/{len(todo)}  ok={ok}  errors={err}")

    msg = f"[asm] Done — {ok} compiled"
    if err:
        msg += f", {err} errors"
    print(msg)


# ── Phase 4: gem5 window check ───────────────────────────────────────────────

# Per-transmitter-type checker scripts.
# Each xmit_kind from the annotation JSON maps to a checker script that
# implements the right window check for that transmitter type.
_KIND_TO_CHECKER = {
    "ld":      "check_ld.py",       # load → cache state leak at complete
    "br_x":    "check_br.py",       # branch → fetch redirect at resolution
    "other_x": "check_other.py",    # variable-latency → timing at complete
}
# Fallback: kinds that don't have a specialised checker use the load check
# (most conservative — checks complete in retirement window).
_DEFAULT_CHECKER = "check_ld.py"

# Legacy single-script mode (pipeline.check != "per_type").
_LEGACY_SCRIPTS = {
    "window_complete": "pipeline_window_complete.py",
    "window_issue":    "pipeline_window.py",
    "completion_only": "pipeline.py",
}


def _read_xmit_kind(ann_dir: Path, stem: str) -> str:
    """Read xmit.kind from an annotation file, defaulting to 'ld'."""
    ann_path = ann_dir / (stem + ".ann.json")
    try:
        ann = json.loads(ann_path.read_text())
        return ann.get("xmit", {}).get("kind", "ld")
    except Exception:
        return "ld"


def _run_checker_batch(checker: Path, s_files: list, ann_dir: Path,
                       batch_out: Path, scheme: int, jobs: int,
                       keep_tmp: bool) -> subprocess.CompletedProcess:
    """Copy .s + .ann.json into a temp dir and invoke a checker script."""
    with tempfile.TemporaryDirectory(prefix="simspect_gem5_") as tmp:
        tmp_path = Path(tmp)
        for sf in s_files:
            shutil.copy(sf, tmp_path / sf.name)
            ann_src = ann_dir / (sf.stem + ".ann.json")
            if ann_src.exists():
                shutil.copy(ann_src, tmp_path / ann_src.name)

        cmd = [
            sys.executable, str(checker),
            str(tmp_path),
            "--jobs",   str(jobs),
            "--out",    str(batch_out),
            "--scheme", str(scheme),
        ]
        if keep_tmp:
            cmd.append("--keep-tmp")

        return subprocess.run(cmd, check=False, capture_output=True, text=True)


def _collect_batch_results(batch_out: Path, existing: list,
                           already_done: set, hits_f: Path,
                           batch_label: str) -> int:
    """Read batch output, append to existing results, return hit count."""
    if not batch_out.exists():
        print(f"  [warn] {batch_label} produced no output file")
        return 0

    batch_results = json.loads(batch_out.read_text())
    batch_hits = [r["name"] for r in batch_results
                  if r.get("issued_in_window") is True]
    batch_errs = sum(1 for r in batch_results if r.get("status") != "ok")

    for r in batch_results:
        if r.get("status") == "error":
            err_msg = (r.get("error") or "")[:160]
            print(f"    [err] {r['name']}: {err_msg}")

    if batch_hits:
        with hits_f.open("a") as fh:
            fh.write("\n".join(batch_hits) + "\n")

    existing.extend(batch_results)
    already_done.update(r["name"] for r in batch_results)

    if batch_errs:
        print(f"    hits={len(batch_hits)}  errors={batch_errs}")
    elif batch_hits:
        print(f"    hits={len(batch_hits)}")

    return len(batch_hits)


def phase_gem5(cfg: dict, model: str, out_base: Path, force: bool) -> None:
    asm_dir     = out_base / "asm"
    ann_dir     = out_base / "ann"
    results_dir = out_base / "results"

    s_files = sorted(asm_dir.glob("*.s")) if asm_dir.exists() else []
    if not s_files:
        sys.exit("error: generated/<model>/asm/ is empty — run the 'asm' phase first")
    if not ann_dir.exists() or not any(ann_dir.glob("*.ann.json")):
        sys.exit("error: generated/<model>/ann/ is empty — run the 'asm' phase first")

    results_dir.mkdir(parents=True, exist_ok=True)
    results_f = results_dir / "window-results.json"
    hits_f    = results_dir / "window-hits.txt"

    # Load any already-completed results so we can skip them.
    if force:
        existing: list = []
        already_done: set = set()
        results_f.write_text("[]")
        hits_f.write_text("")
    elif results_f.exists():
        try:
            existing = json.loads(results_f.read_text())
        except Exception:
            existing = []
        already_done = {r["name"] for r in existing}
    else:
        existing = []
        already_done = set()
        results_f.write_text("[]")
        hits_f.write_text("")

    stage3   = resolve(cfg["paths"]["stage3_dir"])
    gem5_cfg = cfg.get("gem5", {})
    scheme   = gem5_cfg.get("scheme", 2)
    jobs     = gem5_cfg.get("jobs", 8)
    keep_tmp = cfg.get("pipeline", {}).get("keep_tmp", False)
    batch_sz = cfg.get("alloy", {}).get("batch_size", 1000)

    check_mode = cfg.get("pipeline", {}).get("check", "per_type")

    # Determine which tests still need to run.
    to_test = [
        sf for sf in s_files
        if sf.stem not in already_done
        and (ann_dir / (sf.stem + ".ann.json")).exists()
    ]

    if not to_test:
        print(f"[gem5] All {len(already_done)} tests already in results — skipping")
        return

    # ── Legacy single-checker mode ───────────────────────────────────────
    if check_mode != "per_type":
        script_name = _LEGACY_SCRIPTS.get(check_mode, "pipeline_window_complete.py")
        checker = stage3 / script_name

        total_batches = (len(to_test) + batch_sz - 1) // batch_sz
        print(f"[gem5] {len(to_test)} tests → {total_batches} batches "
              f"(checker={script_name}, scheme={scheme}, jobs={jobs})")

        cum_hits = 0
        for bn, start in enumerate(range(0, len(to_test), batch_sz), 1):
            batch = to_test[start : start + batch_sz]
            print(f"\n  Batch {bn}/{total_batches}  "
                  f"({batch[0].stem} … {batch[-1].stem})")
            batch_out = results_dir / f"batch_{bn:04d}_results.json"

            result = _run_checker_batch(checker, batch, ann_dir, batch_out,
                                        scheme, jobs, keep_tmp)
            for line in result.stdout.splitlines():
                if "ERROR" in line or "[err]" in line.lower():
                    print(f"    {line.strip()}")
            if result.stderr.strip():
                for line in result.stderr.strip().splitlines():
                    print(f"    [stderr] {line}")

            cum_hits += _collect_batch_results(
                batch_out, existing, already_done, hits_f,
                f"batch {bn}")
            results_f.write_text(json.dumps(existing, indent=2))
            print(f"  cumulative hits={cum_hits}")

    # ── Per-transmitter-type mode (default) ──────────────────────────────
    else:
        # Group tests by xmit_kind → checker script.
        groups: dict = {}  # checker_script → list of .s paths
        for sf in to_test:
            kind = _read_xmit_kind(ann_dir, sf.stem)
            script = _KIND_TO_CHECKER.get(kind, _DEFAULT_CHECKER)
            groups.setdefault(script, []).append(sf)

        # Print summary of groups.
        print(f"[gem5] {len(to_test)} tests, per-type dispatch "
              f"(scheme={scheme}, jobs={jobs}):")
        for script, files in sorted(groups.items()):
            kinds_in_group = set(_read_xmit_kind(ann_dir, f.stem) for f in files)
            print(f"  {script}: {len(files)} tests  (kinds: {', '.join(sorted(kinds_in_group))})")

        cum_hits = 0
        batch_n = 0

        for script, group_files in sorted(groups.items()):
            checker = stage3 / script
            group_batches = (len(group_files) + batch_sz - 1) // batch_sz
            print(f"\n[gem5:{script}] {len(group_files)} tests → {group_batches} batches")

            for start in range(0, len(group_files), batch_sz):
                batch_n += 1
                batch = group_files[start : start + batch_sz]
                batch_label = f"batch {batch_n} ({script})"
                batch_out = results_dir / f"batch_{batch_n:04d}_results.json"

                print(f"  {batch_label}: {batch[0].stem} … {batch[-1].stem}")

                result = _run_checker_batch(checker, batch, ann_dir, batch_out,
                                            scheme, jobs, keep_tmp)
                for line in result.stdout.splitlines():
                    if "ERROR" in line or "[err]" in line.lower():
                        print(f"    {line.strip()}")
                if result.stderr.strip():
                    for line in result.stderr.strip().splitlines():
                        print(f"    [stderr] {line}")

                cum_hits += _collect_batch_results(
                    batch_out, existing, already_done, hits_f, batch_label)
                results_f.write_text(json.dumps(existing, indent=2))

        print(f"\n  cumulative hits={cum_hits}")

    # ── Final summary ────────────────────────────────────────────────────
    total = len(existing)
    hits  = sum(1 for r in existing if r.get("issued_in_window") is True)
    errs  = sum(1 for r in existing if r.get("status") != "ok")
    print(f"\n[gem5] Done — {hits} hits / {total} total  ({errs} errors)")
    print(f"       Results → {results_f}")
    print(f"       Hits    → {hits_f}")


# ── Clean ─────────────────────────────────────────────────────────────────────

def phase_clean(cfg: dict, model: str, out_base: Path) -> None:
    if out_base.exists():
        print(f"Removing {out_base} …")
        shutil.rmtree(out_base)
        print("Done.")
    else:
        print(f"Nothing to clean: {out_base} does not exist.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "phase",
        choices=["xml", "llvm", "asm", "gem5", "all", "clean"],
        help="Pipeline phase to run",
    )
    ap.add_argument("--model",  required=True,
                    help="Alloy model stem, e.g. STT_4")
    ap.add_argument("--config", default="run_config.jsonc",
                    help="Path to run_config.jsonc (default: run_config.jsonc)")
    ap.add_argument("--force",  action="store_true",
                    help="Re-run phase even if output already exists")
    args = ap.parse_args()

    config_path = ROOT / args.config
    if not config_path.exists():
        sys.exit(f"error: config file not found: {config_path}")

    cfg = load_config(config_path)

    out_dir  = resolve(cfg["paths"]["output_dir"])
    out_base = out_dir / args.model
    out_base.mkdir(parents=True, exist_ok=True)

    phases = (["xml", "llvm", "asm", "gem5"] if args.phase == "all"
              else [args.phase])

    for phase in phases:
        if   phase == "xml":   phase_xml(cfg,  args.model, out_base, args.force)
        elif phase == "llvm":  phase_llvm(cfg, args.model, out_base, args.force)
        elif phase == "asm":   phase_asm(cfg,  args.model, out_base, args.force)
        elif phase == "gem5":  phase_gem5(cfg, args.model, out_base, args.force)
        elif phase == "clean": phase_clean(cfg, args.model, out_base)


if __name__ == "__main__":
    main()
