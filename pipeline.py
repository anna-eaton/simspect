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
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

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
        # speculation.branch_modes (if set) overrides batch_generate's hardcoded
        # RUN_MODES. A single mode writes flat into llvm_dir; multiple modes
        # would write into per-mode subdirs and the downstream phases assume
        # flat layout, so reject that here.
        modes = cfg.get("speculation", {}).get("branch_modes")
        if modes:
            if len(modes) > 1:
                sys.exit(f"error: speculation.branch_modes={modes} — "
                         "phase_llvm only supports one mode per run (the "
                         "asm/ann/results layout is flat). Run separate "
                         "experiments per mode.")
            cmd += ["--mode", modes[0]]
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

    jobs = max(1, int(cfg.get("gem5", {}).get("jobs", 8)))
    print(f"[asm] Compiling {len(todo)}/{len(ll_files)} .ll files  (jobs={jobs}) …")
    ok = err = 0

    # ThreadPoolExecutor (not ProcessPoolExecutor): the heavy work is in
    # subprocess.run (the clang+nm+objdump children), so threads give us
    # real parallelism. ProcessPoolExecutor would need a top-level function
    # to dispatch (closures aren't picklable).
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _one(ll_path_str: str) -> tuple[str, int, str]:
        r = subprocess.run(
            [
                sys.executable,
                str(stage2 / "compile_annotate.py"),
                ll_path_str,
                "--out-dir", str(asm_dir),
                "--ann-dir", str(ann_dir),
            ],
            capture_output=True, text=True,
        )
        return (ll_path_str, r.returncode, r.stderr.strip()[:200])

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = [ex.submit(_one, str(ll)) for ll in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                ll_path_str, rc, stderr_snippet = fut.result()
            except Exception as e:
                err += 1
                print(f"  [exc] worker raised: {e}")
                continue
            if rc == 0:
                ok += 1
            else:
                err += 1
                # Print only first few errors to keep output manageable
                if err <= 20:
                    print(f"  [err] {Path(ll_path_str).name}: {stderr_snippet}")
                elif err == 21:
                    print(f"  [err] (suppressing further per-file errors)")
            if i % 500 == 0:
                print(f"  progress: {i}/{len(todo)}  ok={ok}  errors={err}")

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


# ── Resolution-stall sweep helpers ────────────────────────────────────────────
#
# Sweep runs each test under several `resolve_stall_cycles` assignments
# (joint Cartesian product across resolved branches) and aggregates per-test
# as OR over grid points. The existing checker infrastructure is reused: each
# grid point synthesises a variant `<stem>__sw_<idx>.s/.ann.json` pair, the
# variants are run as ordinary tests, and per-stem aggregation happens
# post-hoc in this module.

import itertools


def _classify_branches(ann: dict) -> tuple[list, list]:
    """Return (resolved_pcs, unresolved_pcs) from an annotation dict.

    resolved   = mode == "correctly_not_taken"   (BTB predicts fall-through,
                 architecturally falls through; stall sweeps timing only)
    unresolved = mode in {"mispredict_not_taken", "mispredict_taken"}
                 (BTB-forced wrong direction; held by a single large stall)
    """
    resolved, unresolved = [], []
    for entry in ann.get("annotations", []):
        pc = entry.get("branch_pc")
        if pc is None:
            continue
        mode = entry.get("mode", "")
        if mode == "correctly_not_taken":
            resolved.append(pc)
        elif mode in ("mispredict_not_taken", "mispredict_taken"):
            unresolved.append(pc)
    return resolved, unresolved


def _grid_points(resolved_pcs: list, points: list) -> list:
    """Joint Cartesian product: list of {branch_pc → stall_cycles} dicts.

    Empty `resolved_pcs` yields a single empty assignment so unresolved-only
    tests still go through the sweep path (one grid point, only unresolved
    stall applied).
    """
    if not resolved_pcs:
        return [{}]
    return [
        dict(zip(resolved_pcs, combo))
        for combo in itertools.product(points, repeat=len(resolved_pcs))
    ]


def _inject_stalls(ann: dict, stalls: dict, unresolved_stall: int) -> dict:
    """Return a new ann dict with `resolve_stall_cycles` set per branch.

    Resolved branches: stall = stalls[branch_pc] (from grid point).
    Unresolved branches: stall = unresolved_stall (constant).
    """
    out = json.loads(json.dumps(ann))  # deep copy
    for entry in out.get("annotations", []):
        pc = entry.get("branch_pc")
        if pc is None:
            continue
        mode = entry.get("mode", "")
        if mode == "correctly_not_taken":
            entry["resolve_stall_cycles"] = int(stalls.get(pc, 0))
        elif mode in ("mispredict_not_taken", "mispredict_taken"):
            entry["resolve_stall_cycles"] = int(unresolved_stall)
    return out


def _enumerate_grid_for_corpus(s_files: list, ann_dir: Path,
                               sweep_cfg: dict) -> tuple[list, dict, int]:
    """Inspect each test's resolved-branch set and decide its grid.

    Returns (grids, manifest, max_grid_size):
        grids        : list of (s_path, ann_path, grid_index, stalls_dict)
                       — flattened across tests, then ordered for batching.
        manifest     : { base_stem -> [stalls_dict_for_grid_idx_0, ...] }
        max_grid_size: the largest per-test grid (sets the number of batches
                       to run). Tests with smaller grids contribute to
                       earlier batches only.
    """
    points = sweep_cfg.get("points", [0])

    manifest: dict = {}
    per_grid_idx: dict = {}   # grid_idx -> list of (s_path, ann_path, stalls)

    for sf in s_files:
        ann_path = ann_dir / (sf.stem + ".ann.json")
        if not ann_path.exists():
            continue
        ann = json.loads(ann_path.read_text())
        resolved, _ = _classify_branches(ann)
        grid = _grid_points(resolved, points)
        manifest[sf.stem] = grid

        for idx, stalls in enumerate(grid):
            per_grid_idx.setdefault(idx, []).append((sf, ann_path, stalls))

    if not per_grid_idx:
        return [], manifest, 0

    max_grid_size = max(per_grid_idx.keys()) + 1
    return per_grid_idx, manifest, max_grid_size


def _materialise_grid_run(grid_entries: list, variant_dir: Path,
                          unresolved_stall: int) -> list:
    """For one grid index, materialise per-test .s/.ann.json under variant_dir.

    Each test keeps its original stem (so the per-test entry stub in the
    checker links correctly). Variant differentiation comes from running
    each grid index as a separate batch.

    Returns list of variant .s Paths under variant_dir.
    """
    variant_dir.mkdir(parents=True, exist_ok=True)
    s_paths: list = []

    for sf, ann_path, stalls in grid_entries:
        v_s = variant_dir / sf.name
        if v_s.exists() or v_s.is_symlink():
            v_s.unlink()
        v_s.symlink_to(sf.resolve())

        v_ann = variant_dir / (sf.stem + ".ann.json")
        ann = json.loads(ann_path.read_text())
        v_ann.write_text(json.dumps(
            _inject_stalls(ann, stalls, unresolved_stall), indent=2))

        s_paths.append(v_s)

    return s_paths


def _aggregate_sweep_results(per_grid_results: dict, manifest: dict,
                              sweep_dir: Path) -> list:
    """Reduce per-grid-index results to per-stem results.

    per_grid_results: { grid_idx -> [list of result dicts from that batch] }
    manifest:         { base_stem -> [stalls_dict per grid_idx, ...] }

    Returns aggregated list (one row per base stem) for window-results.json
    and writes per-stem sweep sidecars.
    """
    aggregated: list = []

    for base_stem, grid in manifest.items():
        per_grid_summary = []
        any_hit = False
        any_err = False
        triggered = []

        for idx, stalls in enumerate(grid):
            batch_results = per_grid_results.get(idx, [])
            row = next((r for r in batch_results
                        if r.get("name") == base_stem), None)
            if row is None:
                per_grid_summary.append({"stalls": stalls, "result": None})
                any_err = True
                continue
            hit = bool(row.get("issued_in_window"))
            status = row.get("status", "unknown")
            per_grid_summary.append({
                "stalls":           stalls,
                "issued_in_window": hit,
                "status":           status,
            })
            if hit:
                any_hit = True
                triggered.append(stalls)
            if status not in ("ok", None):
                any_err = True

        sidecar = sweep_dir / (base_stem + "_sweep.json")
        sidecar.write_text(json.dumps({
            "stem":             base_stem,
            "grid_points":      per_grid_summary,
            "triggered_points": triggered,
        }, indent=2))

        aggregated.append({
            "name":             base_stem,
            "issued_in_window": any_hit,
            "status":           "ok" if not any_err else "error",
            "sweep_grid_size":  len(grid),
            "sweep_triggered":  len(triggered),
        })

    return aggregated


def _build_gem5_env(gem5_cfg: dict, spec_cfg: dict) -> dict:
    """Derive env vars that gem5_common.py honors from run_config.jsonc."""
    env = os.environ.copy()

    binary = gem5_cfg.get("binary")
    cfg_script = gem5_cfg.get("config_script")
    cpu = gem5_cfg.get("cpu_type")
    dbg_flags = gem5_cfg.get("debug_flags")
    dbg_file = gem5_cfg.get("debug_file")

    if binary:
        env["SIMSPECT_GEM5_BIN"] = str(binary)
        # Derive the gem5 tree root (cwd for gem5) from build/<ISA>/gem5.opt
        bpath = Path(binary)
        if "build" in bpath.parts:
            idx = bpath.parts.index("build")
            env["SIMSPECT_GEM5_DIR"] = str(Path(*bpath.parts[:idx]))
    if cfg_script:
        env["SIMSPECT_SE_CONFIG"] = str(cfg_script)
    if cpu:
        env["SIMSPECT_GEM5_CPU"] = str(cpu)
    if isinstance(dbg_flags, list) and dbg_flags:
        env["SIMSPECT_GEM5_DBG_FLAG"] = ",".join(str(f) for f in dbg_flags)
    if dbg_file:
        env["SIMSPECT_GEM5_DBG_FILE"] = str(dbg_file)

    # Explicit opt-in: only inject --branch-ann-file when the configured gem5
    # binary actually supports it (i.e. the gem5-recon-modded build). The
    # speculation.control_flow switch alone is not enough, since a user may
    # keep control_flow=true while pointing at a vanilla gem5 build.
    if gem5_cfg.get("branch_ann_enable"):
        env["SIMSPECT_BRANCH_ANN_ENABLE"] = "1"

    if gem5_cfg.get("allow_leaked"):
        env["SIMSPECT_ALLOW_LEAKED"] = "1"

    return env


def _run_checker_batch(checker: Path, s_files: list, ann_dir: Path,
                       batch_out: Path, scheme: int, jobs: int,
                       keep_tmp: bool,
                       env: Optional[dict] = None) -> subprocess.CompletedProcess:
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

        return subprocess.run(cmd, check=False, capture_output=True, text=True,
                              env=env)


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


def _phase_gem5_sweep(cfg: dict, model: str, out_base: Path, force: bool,
                      s_files: list, ann_dir: Path,
                      results_dir: Path) -> None:
    """Sweep variant of phase_gem5: each test is run under several
    `resolve_stall_cycles` assignments (joint Cartesian product across its
    resolved branches). Per-test verdict is OR over grid points.

    Reuses the existing per-type checker infrastructure by synthesising
    variant .s/.ann.json pairs in a sweep/ subdirectory and feeding them as
    ordinary tests.
    """
    sweep_cfg = cfg.get("sweep", {})

    sweep_dir   = out_base / "sweep"
    variant_dir = sweep_dir / "variants"
    raw_dir     = sweep_dir / "raw_results"
    sweep_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    results_f = results_dir / "window-results.json"
    hits_f    = results_dir / "window-hits.txt"

    if not force and results_f.exists():
        print(f"[gem5:sweep] {results_f.name} already exists — pass --force to "
              "re-run sweep")
        return

    stage3   = resolve(cfg["paths"]["stage3_dir"])
    gem5_cfg = cfg.get("gem5", {})
    spec_cfg = cfg.get("speculation", {})
    scheme   = gem5_cfg.get("scheme", 2)
    jobs     = gem5_cfg.get("jobs", 8)
    keep_tmp = cfg.get("pipeline", {}).get("keep_tmp", False)
    batch_sz = cfg.get("alloy", {}).get("batch_size", 1000)
    checker_env = _build_gem5_env(gem5_cfg, spec_cfg)

    # Enumerate the per-test grid (resolved-branch joint product).
    per_grid_idx, manifest, max_grid = _enumerate_grid_for_corpus(
        s_files, ann_dir, sweep_cfg)
    (sweep_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    n_runs = sum(len(entries) for entries in per_grid_idx.values()) \
             if isinstance(per_grid_idx, dict) else 0
    print(f"[gem5:sweep] {len(manifest)} tests × variable grid (max {max_grid} "
          f"points) → {n_runs} variant runs  "
          f"(points={sweep_cfg.get('points')}, "
          f"unresolved_stall={sweep_cfg.get('unresolved_stall_cycles')})")

    unresolved_stall = int(sweep_cfg.get("unresolved_stall_cycles", 0))

    # One batch (or batch group) per grid index. Within a grid index, dispatch
    # tests by xmit_kind so the per_type checker mapping continues to work.
    per_grid_results: dict = {}
    batch_n = 0
    for grid_idx in sorted(per_grid_idx.keys()):
        entries = per_grid_idx[grid_idx]
        # Materialise this grid index in its own subdir (preserves base stems
        # so the per-test entry-stub linker call works).
        grid_subdir = variant_dir / f"point_{grid_idx:04d}"
        run_files = _materialise_grid_run(entries, grid_subdir,
                                          unresolved_stall)

        # Group by xmit_kind for per_type dispatch.
        groups: dict = {}
        for vf in run_files:
            kind = _read_xmit_kind(ann_dir, vf.stem)
            script = _KIND_TO_CHECKER.get(kind, _DEFAULT_CHECKER)
            groups.setdefault(script, []).append(vf)

        grid_raw: list = []
        for script, files in sorted(groups.items()):
            checker = stage3 / script
            for start in range(0, len(files), batch_sz):
                batch_n += 1
                batch = files[start : start + batch_sz]
                batch_out = raw_dir / f"grid{grid_idx:04d}_batch{batch_n:04d}_{script}.json"

                print(f"  grid {grid_idx} ({script}): "
                      f"{batch[0].stem} … {batch[-1].stem}  ({len(batch)} tests)")

                result = _run_checker_batch(checker, batch, grid_subdir,
                                            batch_out, scheme, jobs, keep_tmp,
                                            env=checker_env)
                for line in result.stdout.splitlines():
                    if "ERROR" in line or "[err]" in line.lower():
                        print(f"    {line.strip()}")
                if result.stderr.strip():
                    for line in result.stderr.strip().splitlines():
                        print(f"    [stderr] {line}")

                if batch_out.exists():
                    grid_raw.extend(json.loads(batch_out.read_text()))

        per_grid_results[grid_idx] = grid_raw

    # Aggregate per-stem and write window-results.json.
    aggregated = _aggregate_sweep_results(per_grid_results, manifest, sweep_dir)
    results_f.write_text(json.dumps(aggregated, indent=2))

    hits = [r["name"] for r in aggregated if r.get("issued_in_window")]
    if hits:
        hits_f.write_text("\n".join(hits) + "\n")
    else:
        hits_f.write_text("")

    errs = sum(1 for r in aggregated if r.get("status") != "ok")
    print(f"\n[gem5:sweep] Done — {len(hits)} hits / {len(aggregated)} tests "
          f"({errs} errors)  across {n_runs} variant runs")
    print(f"             Results       → {results_f}")
    print(f"             Per-test sweep → {sweep_dir}/<stem>_sweep.json")


def phase_gem5(cfg: dict, model: str, out_base: Path, force: bool) -> None:
    asm_dir     = out_base / "asm"
    ann_dir     = out_base / "ann"
    results_dir = out_base / "results"

    s_files = sorted(asm_dir.glob("*.s")) if asm_dir.exists() else []
    if not s_files:
        sys.exit("error: generated/<model>/asm/ is empty — run the 'asm' phase first")
    if not ann_dir.exists() or not any(ann_dir.glob("*.ann.json")):
        sys.exit("error: generated/<model>/ann/ is empty — run the 'asm' phase first")

    if cfg.get("sweep", {}).get("enabled"):
        if not cfg.get("gem5", {}).get("branch_ann_enable"):
            sys.exit("error: sweep.enabled requires gem5.branch_ann_enable: true "
                     "(modded gem5 build)")
        return _phase_gem5_sweep(cfg, model, out_base, force,
                                 s_files, ann_dir, results_dir)

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
    spec_cfg = cfg.get("speculation", {})
    scheme   = gem5_cfg.get("scheme", 2)
    jobs     = gem5_cfg.get("jobs", 8)
    keep_tmp = cfg.get("pipeline", {}).get("keep_tmp", False)
    batch_sz = cfg.get("alloy", {}).get("batch_size", 1000)

    checker_env = _build_gem5_env(gem5_cfg, spec_cfg)

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
                                        scheme, jobs, keep_tmp,
                                        env=checker_env)
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
                                            scheme, jobs, keep_tmp,
                                            env=checker_env)
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
