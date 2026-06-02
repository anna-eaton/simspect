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

Output layout:
    testsets/<model>/
        xml/        inst-*.xml, inst-*.txt
        <mode>/
            llvm/   inst-*.ll (+ bare inst-*.ann.json)
            asm/    inst-*.s, inst-*.o
            ann/    inst-*.ann.json (resolved x86 offsets)

    results/<results_name>/
        <mode>/
            results/  window-results.json, window-hits.txt, batch_NNNN_results.json
            hits/     hitting .s files copied here after gem5 sweep
            sweep/    per-stem sweep sidecars
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
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


# ── Provenance snapshot ───────────────────────────────────────────────────────

def save_provenance(cfg: dict, model: str, testset_base: Path,
                    config_path: Path) -> None:
    """Archive the exact parsexml.py, Alloy model, and run config into
    testset_base/provenance.tar.gz so the testset is self-describing.
    Skipped if the archive already exists.
    """
    out = testset_base / "provenance.tar.gz"
    if out.exists():
        return

    parsexml = resolve(cfg["paths"]["stage2_dir"]) / "parsexml.py"
    model_file = resolve(cfg["paths"]["models_dir"]) / f"{model}.als"

    sources = [
        (parsexml,    "parsexml.py"),
        (model_file,  model_file.name),
        (config_path, config_path.name),
    ]

    testset_base.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tf:
        for src, arcname in sources:
            if src.exists():
                tf.add(src, arcname=arcname)

    present = [arcname for src, arcname in sources if src.exists()]
    print(f"[provenance] Saved {out.name}  ({', '.join(present)})")


# ── Phase 1: Alloy → XML ──────────────────────────────────────────────────────

def phase_xml(cfg: dict, model: str, out_base: Path, force: bool) -> None:
    xml_dir = out_base / "xml"
    if not force and xml_dir.exists() and any(xml_dir.glob("inst-*.xml")):
        n = sum(1 for _ in xml_dir.glob("inst-*.xml"))
        print(f"[xml] {xml_dir.name}/ already has {n} instances — skipping "
              f"(pass --force to re-enumerate)")
        return

    if force and xml_dir.exists():
        for old in xml_dir.glob("inst-*.xml"):
            old.unlink()
        for old in xml_dir.glob("inst-*.txt"):
            old.unlink()
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

def phase_llvm(cfg: dict, model: str, out_base: Path, force: bool,
               mode: Optional[str] = None,
               xml_dir_override: Optional[Path] = None) -> None:
    xml_dir  = xml_dir_override or (out_base / "xml")
    llvm_dir = out_base / "llvm"

    xml_files = sorted(xml_dir.glob("inst-*.xml")) if xml_dir.exists() else []
    if not xml_files:
        sys.exit("error: generated/<model>/xml/ is empty — run the 'xml' phase first")

    llvm_dir.mkdir(parents=True, exist_ok=True)

    stage2       = resolve(cfg["paths"]["stage2_dir"])
    tables_path  = resolve(cfg["paths"]["instruction_tables"])

    # Determine expected output suffix (variant mode changes stem to <stem>_v0)
    interleave_cfg = cfg.get("interleave", {})
    il_variants = (int(interleave_cfg.get("variants_per_instance", 1))
                   if interleave_cfg.get("enabled") else 1)
    done_suffix = "_v0.ll" if il_variants > 1 else ".ll"

    if force:
        todo = xml_files
    else:
        todo = [f for f in xml_files if not (llvm_dir / (f.stem + done_suffix)).exists()]

    if not todo:
        done = sum(1 for f in xml_files if (llvm_dir / (f.stem + done_suffix)).exists())
        print(f"[llvm] All {done} .ll files already generated — skipping")
        return

    mode_label = f" [{mode}]" if mode else ""
    print(f"[llvm]{mode_label} Generating LLVM IR for {len(todo)}/{len(xml_files)} instances …")

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
        # When mode is set explicitly (multi-mode run), pass it directly.
        # Otherwise fall back to speculation.branch_modes from config.
        if mode:
            cmd += ["--mode", mode]
        else:
            cfg_modes = cfg.get("speculation", {}).get("branch_modes")
            if cfg_modes and len(cfg_modes) == 1:
                cmd += ["--mode", cfg_modes[0]]
        if interleave_cfg:
            cmd += ["--interleave-config", json.dumps(interleave_cfg)]
        result = subprocess.run(cmd, cwd=str(stage2),
                                capture_output=True, text=True)
        # Print only error/skip lines from batch_generate
        for line in result.stdout.splitlines():
            if "[err]" in line or "[skip]" in line:
                print(f"  {line.strip()}")
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            sys.exit(f"error: batch_generate.py failed (exit {result.returncode})")

    done = sum(1 for f in xml_files if (llvm_dir / (f.stem + done_suffix)).exists())
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

def _read_xmit_kind(ann_dir: Path, stem: str) -> str:
    """Read xmit.kind from an annotation file. Raises if the file is missing,
    unparseable, or lacks xmit.kind — silent fallback misroutes tests to
    check_ld and hides upstream pipeline breakage."""
    ann_path = ann_dir / (stem + ".ann.json")
    ann = json.loads(ann_path.read_text())
    kind = ann.get("xmit", {}).get("kind")
    if not kind:
        raise ValueError(f"{ann_path}: missing xmit.kind")
    return kind


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
    xmit_pc = ann.get("xmit", {}).get("pc")
    resolved, unresolved = [], []
    for entry in ann.get("annotations", []):
        pc = entry.get("branch_pc")
        if pc is None or pc == xmit_pc:
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

    xmit branch (pc == ann["xmit"]["pc"]): stall = 0. The xmit's own
        resolution must not be held back; the speculation window comes from
        upstream unresolved branches, not from the xmit itself.
    Resolved branches: stall = stalls[branch_pc] (from grid point).
    Unresolved branches: stall = unresolved_stall (constant).
    """
    out = json.loads(json.dumps(ann))  # deep copy
    xmit_pc = out.get("xmit", {}).get("pc")
    for entry in out.get("annotations", []):
        pc = entry.get("branch_pc")
        if pc is None:
            continue
        if pc == xmit_pc:
            entry["resolve_stall_cycles"] = 0
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

    fnc_stall = gem5_cfg.get("fnc_commit_stall_cycles", 0)
    if fnc_stall:
        env["SIMSPECT_FNC_COMMIT_STALL_CYCLES"] = str(int(fnc_stall))

    extra = gem5_cfg.get("extra_args")
    if isinstance(extra, list) and extra:
        env["SIMSPECT_GEM5_EXTRA"] = "\x1f".join(str(a) for a in extra)

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


def _phase_gem5_sweep(cfg: dict, model: str, ts_mode: Path, rs_mode: Path,
                      force: bool, s_files: list, ann_dir: Path) -> None:
    """Sweep variant of phase_gem5."""
    sweep_cfg = cfg.get("sweep", {})

    sweep_dir   = rs_mode / "sweep"
    variant_dir = sweep_dir / "variants"
    raw_dir     = sweep_dir / "raw_results"
    sweep_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    rs_mode.mkdir(parents=True, exist_ok=True)

    results_f = rs_mode / "window-results.json"
    hits_f    = rs_mode / "window-hits.txt"

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

    aggregated = _aggregate_sweep_results(per_grid_results, manifest, sweep_dir)
    results_f.write_text(json.dumps(aggregated, indent=2))

    hits = [r["name"] for r in aggregated if r.get("issued_in_window")]
    if hits:
        hits_f.write_text("\n".join(hits) + "\n")
    else:
        hits_f.write_text("")

    # Copy hitting .s files to hits/ subdirectory for easy inspection.
    hits_dir = rs_mode / "hits"
    if hits:
        hits_dir.mkdir(parents=True, exist_ok=True)
        for stem in hits:
            src = ts_mode / "asm" / (stem + ".s")
            if src.exists():
                shutil.copy(src, hits_dir / src.name)
        print(f"             Hits copied    → {hits_dir}/  ({len(hits)} files)")

    errs = sum(1 for r in aggregated if r.get("status") != "ok")
    print(f"\n[gem5:sweep] Done — {len(hits)} hits / {len(aggregated)} tests "
          f"({errs} errors)  across {n_runs} variant runs")
    print(f"             Results  → {results_f}")
    print(f"             Sweep    → {sweep_dir}/<stem>_sweep.json")


# ── Streaming asm+gem5 ───────────────────────────────────────────────────────

def phase_asm_gem5_streaming(cfg: dict, model: str, ts_mode: Path,
                              rs_mode: Path, force: bool) -> None:
    """Compile .ll → .s in batches and immediately run gem5 on each batch.

    Replaces the sequential asm-then-gem5 flow when both phases are requested
    (i.e. `pipeline.py all`). gem5 starts on the first batch while the second
    batch is still compiling, hiding compile latency behind gem5 runtime.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    llvm_dir = ts_mode / "llvm"
    asm_dir  = ts_mode / "asm"
    ann_dir  = ts_mode / "ann"

    ll_files = sorted(llvm_dir.glob("*.ll")) if llvm_dir.exists() else []
    if not ll_files:
        sys.exit("error: testsets/<model>/llvm/ is empty — run the 'llvm' phase first")

    asm_dir.mkdir(parents=True, exist_ok=True)
    ann_dir.mkdir(parents=True, exist_ok=True)
    rs_mode.mkdir(parents=True, exist_ok=True)

    stage2      = resolve(cfg["paths"]["stage2_dir"])
    stage3      = resolve(cfg["paths"]["stage3_dir"])
    gem5_cfg    = cfg.get("gem5", {})
    sweep_cfg   = cfg.get("sweep", {})
    scheme      = gem5_cfg.get("scheme", 2)
    jobs        = max(1, int(gem5_cfg.get("jobs", 8)))
    keep_tmp    = cfg.get("pipeline", {}).get("keep_tmp", False)
    batch_sz    = cfg.get("alloy", {}).get("batch_size", 1000)
    checker_env = _build_gem5_env(gem5_cfg, cfg.get("speculation", {}))
    sweep_on    = sweep_cfg.get("enabled", False)
    sample_frac = float(gem5_cfg.get("sample_fraction", 1.0))
    if sample_frac < 1.0:
        sys.path.insert(0, str(resolve(cfg["paths"]["stage3_dir"])))
        from gem5_common import sample_keep as _sample_keep
    else:
        _sample_keep = None

    if sweep_on and not gem5_cfg.get("branch_ann_enable"):
        sys.exit("error: sweep.enabled requires gem5.branch_ann_enable: true")

    # ── results state ────────────────────────────────────────────────────────
    results_f = rs_mode / "window-results.json"
    hits_f    = rs_mode / "window-hits.txt"
    hits_dir  = rs_mode / "hits"

    if force:
        existing: list = []
        already_gem5: set = set()
        results_f.write_text("[]")
        hits_f.write_text("")
    elif results_f.exists():
        try:
            existing = json.loads(results_f.read_text())
        except Exception:
            existing = []
        already_gem5 = {r["name"] for r in existing}
    else:
        existing = []
        already_gem5 = set()
        results_f.write_text("[]")
        hits_f.write_text("")

    # ── sweep state ──────────────────────────────────────────────────────────
    if sweep_on:
        points           = sweep_cfg.get("points", [0])
        unresolved_stall = int(sweep_cfg.get("unresolved_stall_cycles", 0))
        sweep_dir        = rs_mode / "sweep"
        variant_dir      = sweep_dir / "variants"
        raw_dir          = sweep_dir / "raw_results"
        manifest: dict   = {}
        sweep_dir.mkdir(parents=True,  exist_ok=True)
        raw_dir.mkdir(parents=True,    exist_ok=True)
        variant_dir.mkdir(parents=True, exist_ok=True)

    gem5_run_n = [0]  # unique counter for batch output files

    def _copy_hits(stems):
        if not stems:
            return
        hits_dir.mkdir(parents=True, exist_ok=True)
        for stem in stems:
            src = asm_dir / (stem + ".s")
            if src.exists():
                shutil.copy(src, hits_dir / src.name)

    def _gem5_on_batch(s_files: list) -> None:
        """Run gem5 on a list of newly compiled .s files."""
        to_test = [sf for sf in s_files
                   if sf.exists()
                   and sf.stem not in already_gem5
                   and (ann_dir / (sf.stem + ".ann.json")).exists()
                   and (_sample_keep is None
                        or _sample_keep(sf.stem, sample_frac))]
        if not to_test:
            return

        if sweep_on:
            # Build per-test grid, group by grid_idx for batching efficiency.
            per_grid: dict = {}
            local_manifest: dict = {}
            for sf in to_test:
                ann = json.loads((ann_dir / (sf.stem + ".ann.json")).read_text())
                resolved, _ = _classify_branches(ann)
                grid = _grid_points(resolved, points)
                local_manifest[sf.stem] = grid
                manifest[sf.stem]       = grid
                for idx, stalls in enumerate(grid):
                    per_grid.setdefault(idx, []).append(
                        (sf, ann_dir / (sf.stem + ".ann.json"), stalls))

            per_grid_results: dict = {}
            for grid_idx in sorted(per_grid.keys()):
                entries    = per_grid[grid_idx]
                grid_subdir = variant_dir / f"g{grid_idx:04d}_r{gem5_run_n[0]:06d}"
                run_files  = _materialise_grid_run(entries, grid_subdir,
                                                   unresolved_stall)
                groups: dict = {}
                for vf in run_files:
                    script = _KIND_TO_CHECKER.get(
                        _read_xmit_kind(ann_dir, vf.stem), _DEFAULT_CHECKER)
                    groups.setdefault(script, []).append(vf)

                grid_raw: list = []
                for script, files in sorted(groups.items()):
                    gem5_run_n[0] += 1
                    batch_out = raw_dir / f"s{gem5_run_n[0]:06d}_g{grid_idx:04d}_{script}.json"
                    _run_checker_batch(stage3 / script, files, grid_subdir,
                                       batch_out, scheme, jobs, keep_tmp,
                                       env=checker_env)
                    if batch_out.exists():
                        grid_raw.extend(json.loads(batch_out.read_text()))
                per_grid_results[grid_idx] = grid_raw

            batch_agg = _aggregate_sweep_results(
                per_grid_results, local_manifest, sweep_dir)
            hits_now = [r["name"] for r in batch_agg if r.get("issued_in_window")]

            existing.extend(batch_agg)
            already_gem5.update(r["name"] for r in batch_agg)
            results_f.write_text(json.dumps(existing, indent=2))
            if hits_now:
                with hits_f.open("a") as fh:
                    fh.write("\n".join(hits_now) + "\n")
                _copy_hits(hits_now)
                print(f"    hits this batch: {len(hits_now)}")

        else:
            # Non-sweep: per-type dispatch.
            groups: dict = {}
            for sf in to_test:
                script = _KIND_TO_CHECKER.get(
                    _read_xmit_kind(ann_dir, sf.stem), _DEFAULT_CHECKER)
                groups.setdefault(script, []).append(sf)
            for script, files in sorted(groups.items()):
                gem5_run_n[0] += 1
                batch_out = rs_mode / f"batch_{gem5_run_n[0]:06d}_results.json"
                _run_checker_batch(stage3 / script, files, ann_dir,
                                   batch_out, scheme, jobs, keep_tmp,
                                   env=checker_env)
                n = _collect_batch_results(batch_out, existing, already_gem5,
                                           hits_f, f"stream {gem5_run_n[0]}")

            results_f.write_text(json.dumps(existing, indent=2))
            # Copy any new hits from this batch.
            if results_f.exists():
                batch_hits = [r["name"] for r in existing
                              if r.get("issued_in_window")
                              and not (hits_dir / (r["name"] + ".s")).exists()]
                _copy_hits(batch_hits)

    # ── compile what isn't done, run gem5 on already-compiled pending ────────
    if force:
        todo_ll = ll_files
    else:
        todo_ll = [f for f in ll_files
                   if not (asm_dir / (f.stem + ".s")).exists()]

    # Already compiled but not yet gem5'd — process first.
    pending_s = [asm_dir / (f.stem + ".s")
                 for f in ll_files
                 if (asm_dir / (f.stem + ".s")).exists()
                 and f.stem not in already_gem5]
    if pending_s:
        print(f"[stream] gem5 on {len(pending_s)} already-compiled tests ...")
        for start in range(0, len(pending_s), batch_sz):
            _gem5_on_batch(pending_s[start:start + batch_sz])

    # Main loop: compile a batch → gem5 that batch → repeat.
    def _compile_one(ll_path):
        r = subprocess.run(
            [sys.executable, str(stage2 / "compile_annotate.py"), str(ll_path),
             "--out-dir", str(asm_dir), "--ann-dir", str(ann_dir)],
            capture_output=True, text=True)
        return ll_path, r.returncode, r.stderr.strip()[:200]

    n_compiled = len(ll_files) - len(todo_ll)
    n_err      = 0
    print(f"[stream] {len(ll_files)} total  "
          f"({n_compiled} compiled, {len(todo_ll)} remaining) — "
          f"streaming compile→gem5 in batches of {batch_sz}")

    for b_start in range(0, len(todo_ll), batch_sz):
        batch_ll  = todo_ll[b_start:b_start + batch_sz]
        new_s: list = []

        with ThreadPoolExecutor(max_workers=jobs) as ex:
            futs = [ex.submit(_compile_one, ll) for ll in batch_ll]
            for fut in as_completed(futs):
                ll_path, rc, stderr = fut.result()
                if rc == 0:
                    new_s.append(asm_dir / (ll_path.stem + ".s"))
                    n_compiled += 1
                else:
                    n_err += 1
                    if n_err <= 10:
                        print(f"  [err] {ll_path.name}: {stderr}")

        print(f"  compiled {n_compiled}/{len(ll_files)}  "
              f"({len(new_s)} new)  →  gem5 ...")
        _gem5_on_batch(new_s)

    if sweep_on:
        (sweep_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    total = len(existing)
    hits  = sum(1 for r in existing if r.get("issued_in_window") is True)
    errs  = sum(1 for r in existing if r.get("status") != "ok")
    print(f"\n[stream] Done — {hits} hits / {total} tests  "
          f"({errs} gem5 errors, {n_err} compile errors)")
    print(f"         Results → {results_f}")
    if hits:
        print(f"         Hits    → {hits_dir}/")


def phase_gem5(cfg: dict, model: str, ts_mode: Path, rs_mode: Path,
               force: bool) -> None:
    asm_dir = ts_mode / "asm"
    ann_dir = ts_mode / "ann"

    s_files = sorted(asm_dir.glob("*.s")) if asm_dir.exists() else []
    if not s_files:
        sys.exit("error: testsets/<model>/asm/ is empty — run the 'asm' phase first")
    if not ann_dir.exists() or not any(ann_dir.glob("*.ann.json")):
        sys.exit("error: testsets/<model>/ann/ is empty — run the 'asm' phase first")

    if cfg.get("sweep", {}).get("enabled"):
        if not cfg.get("gem5", {}).get("branch_ann_enable"):
            sys.exit("error: sweep.enabled requires gem5.branch_ann_enable: true "
                     "(modded gem5 build)")
        return _phase_gem5_sweep(cfg, model, ts_mode, rs_mode,
                                 force, s_files, ann_dir)

    rs_mode.mkdir(parents=True, exist_ok=True)
    results_f = rs_mode / "window-results.json"
    hits_f    = rs_mode / "window-hits.txt"

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

    # Determine which tests still need to run.
    to_test = [
        sf for sf in s_files
        if sf.stem not in already_done
        and (ann_dir / (sf.stem + ".ann.json")).exists()
    ]

    if not to_test:
        print(f"[gem5] All {len(already_done)} tests already in results — skipping")
        return

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
            batch_out = rs_mode / f"batch_{batch_n:04d}_results.json"

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

    hit_stems = [r["name"] for r in existing if r.get("issued_in_window") is True]
    if hit_stems:
        hits_dir = rs_mode / "hits"
        hits_dir.mkdir(parents=True, exist_ok=True)
        for stem in hit_stems:
            src = ts_mode / "asm" / (stem + ".s")
            if src.exists():
                shutil.copy(src, hits_dir / src.name)

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

    paths_cfg = cfg["paths"]
    if "testset_dir" in paths_cfg:
        testset_dir  = resolve(paths_cfg["testset_dir"])
        results_dir  = resolve(paths_cfg["results_dir"])
        results_name = paths_cfg.get("results_name", args.model)
    else:
        # Legacy: single output_dir is both testset and results root.
        legacy = resolve(paths_cfg["output_dir"])
        testset_dir = results_dir = legacy
        results_name = args.model

    testset_base = testset_dir / args.model
    results_base = results_dir / results_name
    testset_base.mkdir(parents=True, exist_ok=True)

    save_provenance(cfg, args.model, testset_base, config_path)

    phases = (["xml", "llvm", "asm", "gem5"] if args.phase == "all"
              else [args.phase])

    modes      = cfg.get("speculation", {}).get("branch_modes", [])
    # Use per-mode layout whenever branch_modes is set (even with a single
    # mode), so testsets/<model>/<mode>/ and results/<results_name>/<mode>/
    # are populated consistently — required for the sttbuild watcher and for
    # taken-only / not_taken-only rerun configs. Flat layout is reserved for
    # configs that don't declare branch_modes at all.
    multi_mode = bool(modes)
    streaming  = "asm" in phases and "gem5" in phases

    for phase in phases:
        if phase == "xml":
            phase_xml(cfg, args.model, testset_base, args.force)
        elif phase == "clean":
            phase_clean(cfg, args.model, testset_base)
        elif phase == "asm" and streaming:
            pass  # handled together with gem5 below
        elif phase == "gem5" and streaming:
            if multi_mode:
                for m in modes:
                    ts_mode = testset_base / m
                    rs_mode = results_base / m
                    ts_mode.mkdir(parents=True, exist_ok=True)
                    print(f"\n=== streaming asm+gem5 [{m}] ===")
                    phase_asm_gem5_streaming(cfg, args.model, ts_mode, rs_mode,
                                             args.force)
            else:
                phase_asm_gem5_streaming(cfg, args.model, testset_base,
                                         results_base, args.force)
        elif multi_mode:
            for m in modes:
                ts_mode = testset_base / m
                rs_mode = results_base / m
                ts_mode.mkdir(parents=True, exist_ok=True)
                if phase == "llvm":
                    phase_llvm(cfg, args.model, ts_mode, args.force,
                               mode=m, xml_dir_override=testset_base / "xml")
                elif phase == "asm":
                    phase_asm(cfg, args.model, ts_mode, args.force)
                elif phase == "gem5":
                    phase_gem5(cfg, args.model, ts_mode, rs_mode, args.force)
        else:
            if phase == "llvm":
                phase_llvm(cfg, args.model, testset_base, args.force)
            elif phase == "asm":
                phase_asm(cfg, args.model, testset_base, args.force)
            elif phase == "gem5":
                phase_gem5(cfg, args.model, testset_base, results_base, args.force)


if __name__ == "__main__":
    main()
