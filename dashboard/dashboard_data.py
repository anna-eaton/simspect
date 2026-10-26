#!/usr/bin/env python3
"""
dashboard_data.py — the stdlib-only, pure-data backend for the SimSpect
project dashboard.

This module contains NO web/HTTP/HTML code. It is a set of functions that each
return JSON-serializable dicts/lists describing the live state of the SimSpect
Alloy -> LLVM -> gem5 pipeline (running jobs, the on-disk corpus, gem5 result
campaigns, instruction/fanout tables, per-test features, and the Alloy
execution graph). A separate HTTP server (dashboard.py) imports these functions
and serves their output.

Design rules:
  * Stdlib only. No external pip dependencies.
  * Reuse the canonical helpers rather than duplicating them:
      - simspect_paths  : canonical filesystem locations + resolve()
      - jobs_registry   : the jobs manifest reader/writer
      - sweep_monitor   : discover(), build_progress(), counting helpers, ...
      - pipeline        : load_config()
      - STAGE2 parsexml : Alloy XML parsing + topo-sort + kind mapping
  * Defensive: every public function is wrapped so that a missing dir/file
    yields empty/partial data instead of raising. On a machine with nothing
    generated yet (no testsets/, no results/, no running jobs) every function
    returns a well-formed empty shape.

Run `python3 dashboard_data.py` to execute the built-in selftest.
"""
from __future__ import annotations

import functools
import json
import re
import subprocess
import sys
import threading
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

# This module lives in dashboard/; shared modules live at the repo root. Ensure the
# repo root is importable even if dashboard_data is imported directly (not via dashboard.py).
import os as _os
_REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Canonical helpers ─────────────────────────────────────────────────────────
import simspect_paths as sp
from simspect_paths import (
    ROOT, TESTSETS, RESULTS, MODELS_DIR, RUNCONFIGS,
    INSTRUCTION_TABLES, JOBS_LOGS, resolve,
)

import jobs_registry
import sweep_monitor as sm

# Load sweep_monitor's persistent on-disk count/json-len cache ONCE at import, so a
# dashboard (re)start begins WARM instead of re-scanning ~2M corpus files (cold
# /api/pipeline was ~9s; warm is ~0.01s). pipeline_graph() calls sm.save_caches()
# after it computes so fresh counts persist for the next start.
try:
    sm.load_caches()
except Exception:
    pass

# pipeline.load_config for reading run configs (JSONC).
try:
    from pipeline import load_config as _pipeline_load_config
except Exception:  # pragma: no cover - pipeline import should normally succeed
    _pipeline_load_config = None

# STAGE2 parsexml lives in a sibling package dir; add it to sys.path so we can
# reuse its Alloy-XML parser + topo-sort instead of re-implementing them.
_STAGE2 = str(sp.STAGE2_DIR)
if _STAGE2 not in sys.path:
    sys.path.insert(0, _STAGE2)
try:
    import parsexml as _px
except Exception:  # pragma: no cover
    _px = None


# ── "Open in VSCode" deep links ───────────────────────────────────────────────
# The dashboard usually runs INSIDE the cafe2 container (make dash), so the files
# it shows are container paths. Set SIMSPECT_VSCODE_REMOTE to the VSCode remote
# authority (e.g. "ssh-remote+cafe2") and links open via Remote-SSH; unset (local
# run on the Mac) falls back to a plain file:// link. scripts/sim sets it for `dash`.
VSCODE_REMOTE = _os.environ.get("SIMSPECT_VSCODE_REMOTE", "").strip()


def vscode_uri(abspath) -> str:
    """vscode:// deep link to open `abspath` in VSCode (remote if configured)."""
    p = str(abspath)
    if not p.startswith("/"):
        p = "/" + p
    from urllib.parse import quote
    q = quote(p)  # keep '/', encode spaces etc.
    if VSCODE_REMOTE:
        return f"vscode://vscode-remote/{VSCODE_REMOTE}{q}"
    return f"vscode://file{q}"


# ── Kind -> checker mapping (the research "criterion" per transmitter) ────────
# Keyed by the transmitter kind stored in an annotation's xmit.kind field.
CHECKERS: dict = {
    "ld": {
        "checker": "check_ld.py",
        "criterion": (
            "Load transmitter: the load's address is used speculatively after "
            "the commit boundary; leaks via cache-state change (LSQ 'Executing "
            "load' tick) inside (lc_retire, fnc_retire). Store-forwarding (SLF) "
            "counts; squash does not disqualify."
        ),
    },
    "br_x": {
        "checker": "check_br.py",
        "criterion": (
            "Branch transmitter: a mispredicted branch broadcasts its "
            "squash/fetch-redirect while still speculative and its fall-through "
            "never retires, within (lc_retire, fnc_retire)."
        ),
    },
    "other_x": {
        "checker": "check_other.py",
        "criterion": (
            "Variable-latency ALU transmitter (e.g. zero-skip multiply, integer "
            "divide): its completion tick falls in (lc_retire, fnc_retire); "
            "includes divide-by-zero-fault reclassification."
        ),
    },
}
# Fallback for any kind not explicitly listed above.
_DEFAULT_CHECKER = {
    "checker": "check_ld.py",
    "criterion": CHECKERS["ld"]["criterion"],
}

# Validation: an on-disk test stem, e.g. inst-047231 or inst-047231_v2.
_STEM_RE = re.compile(r"^inst-[A-Za-z0-9_]+$")
# Validation: a model name maps to MODELS_DIR/<model>.als — no path separators.
_MODEL_RE = re.compile(r"^[A-Za-z0-9._-]+$")

_MAX_TEXT_BYTES = 200 * 1024  # file_text cap (~200 KB)


# ── Defensive wrapper ─────────────────────────────────────────────────────────
def _safe(default_factory):
    """Decorator: if the wrapped function raises, log to stderr and return a
    default (from default_factory) so the dashboard never 500s on bad data."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                sys.stderr.write(
                    f"[dashboard_data] {fn.__name__} failed:\n"
                    + traceback.format_exc()
                )
                return default_factory()
        return wrapper
    return deco


def _load_cfg(cfgpath) -> dict:
    """Read a run config (JSONC). Returns {} on any failure."""
    try:
        p = Path(cfgpath)
        if not p.is_absolute():
            p = resolve(cfgpath)
        if _pipeline_load_config is not None:
            return _pipeline_load_config(p)
        return sm.load_jsonc(p)
    except Exception:
        return {}


def checker_for_kind(kind) -> dict:
    """Return {'name', 'criterion'} for a transmitter kind."""
    entry = CHECKERS.get(kind, _DEFAULT_CHECKER)
    return {"name": entry["checker"], "criterion": entry["criterion"]}


# ── Corpus helpers ────────────────────────────────────────────────────────────
def _count(d: Path, suffix: str) -> int:
    return sm.count_suffix(d, suffix)


def _mode_counts(model_dir: Path, mode: str) -> dict:
    """{'mode','llvm','asm','ann'} counts for one <model>/<mode>/ dir."""
    base = model_dir / mode
    return {
        "mode": mode,
        "llvm": _count(base / "llvm", ".ll"),
        "asm": _count(base / "asm", ".s"),
        "ann": _count(base / "ann", ".ann.json"),
    }


def _list_modes(model_dir: Path) -> list:
    """Subdirs of a model dir that are branch-modes (everything but 'xml')."""
    modes = []
    try:
        for d in sorted(model_dir.iterdir()):
            if d.is_dir() and d.name != "xml":
                modes.append(d.name)
    except OSError:
        pass
    return modes


# ══════════════════════════════════════════════════════════════════════════════
# 1. overview
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {"jobs": [], "counts": {"running_gen": 0, "running_sweep": 0,
                                       "corpora": 0, "campaigns": 0}})
def overview() -> dict:
    jobs = jobs_registry.load_jobs()
    running = [j for j in jobs if j.get("status") == "running"]
    running_gen = sum(1 for j in running if j.get("kind") == "gen")
    running_sweep = sum(1 for j in running if j.get("kind") == "sweep")

    corpora = 0
    if TESTSETS.is_dir():
        corpora = sum(1 for d in TESTSETS.iterdir() if d.is_dir())

    # Count distinct campaigns (results_name) from the newest-per-name scan.
    campaigns = len(_campaign_dirs())

    return {
        "jobs": jobs,
        "counts": {
            "running_gen": running_gen,
            "running_sweep": running_sweep,
            "corpora": corpora,
            "campaigns": campaigns,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. generation
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {"items": []})
def generation() -> dict:
    """Running Alloy/gen builds (from ps discovery) + recent gen jobs from the
    manifest. xml_done = on-disk inst-*.xml count; xml_total = config
    alloy.max_instances."""
    items = []
    seen = set()  # (model, config) de-dupe across live + manifest

    builds, _watchers = sm.discover()
    for (model, cfgpath), info in builds.items():
        # gen producers, and pipeline builds whose phase set includes xml.
        is_gen = info.get("kind") == "gen"
        phases = info.get("phases", set())
        if not (is_gen or "xml" in phases or "all" in phases):
            continue
        cfg = _load_cfg(cfgpath)
        xml_done = _count(TESTSETS / model / "xml", ".xml")
        xml_total = int(cfg.get("alloy", {}).get("max_instances", 0) or 0)
        key = (model, str(cfgpath))
        seen.add(key)
        items.append({
            "job_id": None,
            "model": model,
            "config": str(cfgpath),
            "state": "gen" if is_gen else "build",
            "xml_done": xml_done,
            "xml_total": xml_total,
            "etime": info.get("etime"),
            "live": True,
        })

    # Recent gen jobs from the manifest (not necessarily live).
    for j in jobs_registry.load_jobs():
        if j.get("kind") != "gen":
            continue
        model = j.get("model") or ""
        cfgpath = j.get("config")
        key = (model, str(cfgpath))
        if key in seen:
            continue
        seen.add(key)
        cfg = _load_cfg(cfgpath) if cfgpath else {}
        xml_done = _count(TESTSETS / model / "xml", ".xml") if model else 0
        xml_total = int(cfg.get("alloy", {}).get("max_instances", 0) or 0)
        status = j.get("status", "")
        items.append({
            "job_id": j.get("job_id"),
            "model": model,
            "config": cfgpath,
            "state": status,
            "xml_done": xml_done,
            "xml_total": xml_total,
            "etime": None,
            "live": status == "running",
        })

    return {"items": items}


# ══════════════════════════════════════════════════════════════════════════════
# 3. fanout
# ══════════════════════════════════════════════════════════════════════════════
def _campaign_dirs() -> dict:
    """Map results_name -> newest campaign dir (results/<name>__<ts>/).

    A campaign dir is any immediate child of RESULTS matching '<name>__<ts>';
    the newest per results_name (by mtime) wins. Helper/scratch dirs (leading
    underscore) and symlinks (e.g. __latest) are skipped.
    """
    out: dict = {}
    if not RESULTS.is_dir():
        return out
    for d in sorted(RESULTS.iterdir()):
        if (not d.is_dir() or d.is_symlink() or d.name.startswith("_")
                or "__" not in d.name):
            continue
        name = d.name.rsplit("__", 1)[0]
        try:
            mt = d.stat().st_mtime
        except OSError:
            mt = 0.0
        prev = out.get(name)
        if prev is None or mt > prev[1]:
            out[name] = (d, mt)
    return {name: d for name, (d, _mt) in out.items()}


def _bespoke_campaign_dirs() -> dict:
    """Non-timestamped result dirs from bespoke launchers (e.g. the AMuLeT
    InvisiSpec/SpecLFB runs write results/<name>/<mode>/window-results.json with
    NO __ts suffix, so _campaign_dirs misses them). Keyed by dir name."""
    out: dict = {}
    if not RESULTS.is_dir():
        return out
    for d in sorted(RESULTS.iterdir()):
        if (not d.is_dir() or d.is_symlink() or d.name.startswith("_")
                or "__" in d.name):
            continue
        try:
            has = any((sub / "window-results.json").exists()
                      for sub in d.iterdir() if sub.is_dir())
            if not has:
                # bespoke flat layout (e.g. CleanupSpec writes window-results_on.json
                # at the campaign root, no per-mode dirs)
                has = any(f.name.startswith("window-results") and f.suffix == ".json"
                          for f in d.iterdir() if f.is_file())
        except OSError:
            has = False
        if has:
            out[d.name] = d
    return out


def _infer_campaign_model(name: str):
    """Best-effort: the longest testset-model name that prefixes a campaign name
    (so 'STT_6_invisispec_compound' -> 'STT_6')."""
    if not TESTSETS.is_dir():
        return None
    cands = []
    try:
        for d in TESTSETS.iterdir():
            if d.is_dir() and (name == d.name or name.startswith(d.name)):
                cands.append(d.name)
    except OSError:
        pass
    return max(cands, key=len) if cands else None


def _campaign_modes(cdir: Path) -> list:
    """Per-mode, per-kind totals/hits for one campaign dir.

    Layout: <mode>/<kind>/window-results.json (total = record count) and
    <mode>/<kind>/window-hits.txt (hits = non-blank line count). Falls back to
    a flat <mode>/window-results.json (kind = None) for older layouts.
    """
    modes = []
    try:
        mode_dirs = [d for d in sorted(cdir.iterdir())
                     if d.is_dir() and not d.name.startswith("_")]
    except OSError:
        mode_dirs = []
    for md in mode_dirs:
        kinds = []
        kind_results = sorted(md.glob("*/window-results.json"))
        if kind_results:
            for wr in kind_results:
                kdir = wr.parent
                hits_f = kdir / "window-hits.txt"
                kinds.append({
                    "kind": kdir.name,
                    "total": sm.json_len(wr),
                    "hits": _count_lines(hits_f),
                })
        else:
            wr = md / "window-results.json"
            if wr.exists():
                kinds.append({
                    "kind": None,
                    "total": sm.json_len(wr),
                    "hits": _count_lines(md / "window-hits.txt"),
                })
        if kinds:
            modes.append({"mode": md.name, "kinds": kinds})
    return modes


def _count_lines(f: Path) -> int:
    try:
        return sum(1 for ln in f.read_text().splitlines() if ln.strip())
    except OSError:
        return 0
    except Exception:
        return 0


@_safe(lambda: {"producers": [], "campaigns": []})
def fanout() -> dict:
    """Producers = live testsetgen/pipeline builds with per-mode fanout counts.
    Campaigns = newest gem5 result dir per results_name with per-kind rollups."""
    producers = []
    builds, _watchers = sm.discover()
    for (model, cfgpath), info in builds.items():
        cfg = _load_cfg(cfgpath)
        model_dir = TESTSETS / model
        modes_cfg = cfg.get("speculation", {}).get("branch_modes", [])
        # Prefer the config's declared modes; otherwise whatever is on disk.
        mode_names = modes_cfg or _list_modes(model_dir)
        modes = [_mode_counts(model_dir, m) for m in mode_names]
        producers.append({
            "model": model,
            "config": str(cfgpath),
            "state": info.get("kind", "build"),
            "etime": info.get("etime"),
            "xml": _count(model_dir / "xml", ".xml"),
            "modes": modes,
        })

    campaigns = []
    for name, cdir in sorted(_campaign_dirs().items()):
        man = {}
        mp = cdir / "manifest.json"
        if mp.exists():
            try:
                man = json.loads(mp.read_text())
            except Exception:
                man = {}
        campaigns.append({
            "results_name": name,
            "model": man.get("model"),
            "campaign": cdir.name,
            "gem5_binary": man.get("gem5_binary"),
            "started_at": man.get("started_at"),
            "state": "idle",
            "modes": _campaign_modes(cdir),
        })

    return {"producers": producers, "campaigns": campaigns}


# ══════════════════════════════════════════════════════════════════════════════
# 4. corpora
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {"corpora": []})
def corpora() -> dict:
    out = []
    if not TESTSETS.is_dir():
        return {"corpora": out}
    for d in sorted(TESTSETS.iterdir()):
        if not d.is_dir():
            continue
        xml_dir = d / "xml"
        try:
            mtime = xml_dir.stat().st_mtime if xml_dir.exists() else (
                d.stat().st_mtime)
        except OSError:
            mtime = None
        out.append({
            "model": d.name,
            "xml": _count(xml_dir, ".xml"),
            "mtime": mtime,
            "modes": [_mode_counts(d, m) for m in _list_modes(d)],
            "has_provenance": (d / "provenance.tar.gz").exists(),
        })
    return {"corpora": out}


# ══════════════════════════════════════════════════════════════════════════════
# 4b. pipeline_graph — the unified stage view (XML → PROGRAMS → GEM5)
# ══════════════════════════════════════════════════════════════════════════════
# One row per model (lineage); three stage columns. Folds in everything the old
# sweep_monitor CLI showed (stage progress, defense variant, hits by mode×kind).
# NOTE (stub): progress bars are derived from on-disk file counts polled by the
# dashboard. Granular per-process progress (hooking into a running Alloy/parsexml/
# gem5 job) is future work — see wiki/state/DASHBOARD_PLAN.md.

def _model_cap(model: str) -> int:
    """Best-effort Alloy max_instances for a model (its run config)."""
    cand = RUNCONFIGS / f"run_config_{model}.jsonc"
    if cand.exists():
        try:
            return int(_load_cfg(cand).get("alloy", {}).get("max_instances", 0) or 0)
        except Exception:
            pass
    return 0


# TTL + lock so the dashboard's ~8s poll (and a browser's parallel on-load calls)
# SHARE one computation instead of each kicking off a cold ~9s file-count scan — the
# pile-up of concurrent cold scans was what wedged the page on "loading…". With this,
# the first call computes, the rest within TTL return the cached result instantly.
_PG_LOCK = threading.Lock()
_PG_CACHE: dict = {"t": 0.0, "val": None}
_PG_TTL = 5.0


@_safe(lambda: {"models": [], "gem5_orphans": [], "jobs": [], "generated_at": None})
def pipeline_graph() -> dict:
    """Cached entry point for the one-page stage graph (see _pipeline_graph_compute)."""
    now = time.time()
    v = _PG_CACHE["val"]
    if v is not None and (now - _PG_CACHE["t"]) < _PG_TTL:
        return v
    with _PG_LOCK:
        now = time.time()
        v = _PG_CACHE["val"]
        if v is not None and (now - _PG_CACHE["t"]) < _PG_TTL:
            return v  # another thread computed while we waited
        val = _pipeline_graph_compute()
        _PG_CACHE["val"] = val
        _PG_CACHE["t"] = time.time()
        try:
            sm.save_caches()  # persist fresh counts so the next restart is warm
        except Exception:
            pass
        return val


def _pipeline_graph_compute() -> dict:
    """The one-page stage graph. Returns per-model lineages + gem5 campaigns + jobs."""
    jobs = jobs_registry.load_jobs()
    gen_by_model: dict = {}
    for it in generation().get("items", []):
        gen_by_model.setdefault(it.get("model"), it)

    # gem5 campaigns grouped by model (fold in sweep_monitor info: variant + hits)
    gem5_by_model: dict = {}
    gem5_all = []
    # Union of timestamped testrun campaigns + bespoke launcher dirs (AMuLeT
    # InvisiSpec/SpecLFB write results/<name>/<mode>/window-results.json, no __ts).
    all_campaigns = dict(_campaign_dirs())
    for _nm, _d in _bespoke_campaign_dirs().items():
        all_campaigns.setdefault(_nm, _d)
    for name, cdir in sorted(all_campaigns.items()):
        man = {}
        mp = cdir / "manifest.json"
        if mp.exists():
            try:
                man = json.loads(mp.read_text())
            except Exception:
                man = {}
        variant = None
        cfgp = cdir / "run_config.jsonc"
        if cfgp.exists():
            try:
                variant = sm.variant_of(_load_cfg(cfgp).get("gem5", {}))
            except Exception:
                variant = None
        model = man.get("model") or _infer_campaign_model(name)
        node = {
            "id": f"gem5:{name}", "results_name": name, "model": model,
            "campaign": cdir.name, "gem5_binary": man.get("gem5_binary"),
            "variant": variant, "started_at": man.get("started_at"),
            "modes": _campaign_modes(cdir),
        }
        gem5_all.append(node)
        gem5_by_model.setdefault(model, []).append(node)

    models = []
    if TESTSETS.is_dir():
        for d in sorted(TESTSETS.iterdir()):
            if not d.is_dir():
                continue
            model = d.name
            xml_dir = d / "xml"
            xcount = _count(xml_dir, ".xml")
            cap = _model_cap(model) or int(gen_by_model.get(model, {}).get("xml_total") or 0)
            try:
                xmtime = xml_dir.stat().st_mtime if xml_dir.exists() else None
            except OSError:
                xmtime = None
            g = gen_by_model.get(model, {})
            # completeness: <cap ⇒ exhausted (complete); ≥cap ⇒ hit cap (incomplete); unknown cap ⇒ None
            complete = (xcount < cap) if (cap and xcount) else None

            # PROGRAMS: future per-fanout dir (testsets/<model>/programs/<id>/), else per-mode
            progs = []
            prog_dir = d / "programs"
            fdirs = [p for p in sorted(prog_dir.iterdir()) if p.is_dir()] if prog_dir.is_dir() else []
            if fdirs:
                for fp in fdirs:
                    try:
                        amtime = (fp / "asm").stat().st_mtime if (fp / "asm").exists() else None
                    except OSError:
                        amtime = None
                    progs.append({
                        "id": f"prog:{model}:{fp.name}", "model": model, "fanout": fp.name,
                        "llvm": _count(fp / "llvm", ".ll"), "asm": _count(fp / "asm", ".s"),
                        "ann": _count(fp / "ann", ".ann.json"),
                        "expected": xcount or cap,
                        "dirty": bool(xmtime and amtime and amtime < xmtime),
                    })
            else:
                for mode in _list_modes(d):
                    mc = _mode_counts(d, mode)
                    try:
                        amtime = (d / mode / "asm").stat().st_mtime if (d / mode / "asm").exists() else None
                    except OSError:
                        amtime = None
                    progs.append({
                        "id": f"prog:{model}:{mode}", "model": model, "mode": mode,
                        "llvm": mc["llvm"], "asm": mc["asm"], "ann": mc["ann"],
                        "expected": xcount or cap,
                        "dirty": bool(xmtime and amtime and amtime < xmtime),
                    })

            models.append({
                "model": model,
                "xml": {"id": f"xml:{model}", "instances": xcount, "cap": cap,
                        "complete": complete, "mtime": xmtime, "live": bool(g.get("live")),
                        "state": g.get("state"), "etime": g.get("etime"),
                        "has_provenance": (d / "provenance.tar.gz").exists()},
                "programs": progs,
                "gem5": gem5_by_model.get(model, []),
            })

    # gem5 campaigns whose model dir no longer exists (orphans) still shown
    known = {m["model"] for m in models}
    orphans = [n for n in gem5_all if n.get("model") not in known]

    return {"models": models, "gem5_orphans": orphans, "jobs": jobs,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}


# ══════════════════════════════════════════════════════════════════════════════
# 4c. specs — sources of truth (JSON) for the Utilities tab
# ══════════════════════════════════════════════════════════════════════════════
_SPECS_DIR = ROOT / "specs"


@_safe(lambda: {"specs": []})
def specs() -> dict:
    """List the canonical JSON/JSONC sources of truth + their contents."""
    out = []
    catalog = [
        ("transmitter_stage_mapping", _SPECS_DIR / "transmitter_stage_mapping.json",
         "Which pipeline stage each transmitter kind is decided/observed at."),
        ("timing_directives", _SPECS_DIR / "timing_directives.json",
         "Canonical gem5 timing knobs (stalls, delays) and what they mean."),
        ("instruction_table", sp.STAGE2_DIR / "instruction_tables" / "instructions.jsonc",
         "The fanout/decoding table: kinds → concrete instructions + operand slots."),
    ]
    for name, path, desc in catalog:
        rec = {"name": name, "path": str(path), "desc": desc,
               "exists": path.exists(), "vscode": vscode_uri(str(path))}
        if path.exists():
            try:
                rec["text"] = path.read_text(encoding="utf-8")[:200000]
            except Exception as e:
                rec["text"] = f"(error reading: {e})"
        out.append(rec)
    return {"specs": out}


# ══════════════════════════════════════════════════════════════════════════════
# 4d. model_inventory — EVERY .als model (enumerated or not) + source viewer
# ══════════════════════════════════════════════════════════════════════════════
_MODELS_DIR = ROOT / "STAGE1_alloy" / "models"


def _als_defense_family(text: str) -> str:
    # STT protects State; SPT protects Operand; Recon takes a perturbation param.
    if re.search(r"^fun\s+hardware_protection_policy\s*\[", text, re.M):
        return "Recon (parameterized policy)"
    if re.search(r"^fun\s+hardware_protection_policy\s*:\s*Operand", text, re.M):
        return "SPT (operand granularity)"
    if re.search(r"^fun\s+hardware_protection_policy\s*:\s*State", text, re.M):
        return "STT (state/memory granularity)"
    return "?"


def _als_meta(path: Path) -> dict:
    """Parse a .als for scope + transmitters + defense family (best-effort)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m_scope = re.search(r"exactly\s+(\d+)\s+Instruction", text)
    m_leak = re.search(r"^fun\s+leakage_function\s*:\s*Operand\s*\{([^}]*)\}", text, re.M)
    return {
        "instr_scope": (f"exactly {m_scope.group(1)} Instruction" if m_scope else "?"),
        "transmitters": (m_leak.group(1).strip() if m_leak else "?"),
        "defense_family": _als_defense_family(text),
    }


@_safe(lambda: {"models": [], "archived": 0})
def model_inventory() -> dict:
    """Every .als in STAGE1_alloy/models/ — enumerated or not — with metadata and
    its XML corpus size (0 = never enumerated → invisible in the old view)."""
    out = []
    if _MODELS_DIR.is_dir():
        for f in sorted(_MODELS_DIR.glob("*.als")):
            name = f.stem
            is_link = f.is_symlink()
            rec = {"name": name, "symlink_target": (_os.readlink(f) if is_link else None)}
            try:
                rec["bytes"] = f.stat().st_size
            except OSError:
                rec["bytes"] = None
            rec.update(_als_meta(f))
            xml_dir = TESTSETS / name / "xml"
            rec["xml_count"] = _count(xml_dir, ".xml")
            rec["enumerated"] = rec["xml_count"] > 0
            rec["vscode"] = vscode_uri(str(f))
            out.append(rec)
    archived = len(list((_MODELS_DIR / "old_models").glob("*.als"))) if (_MODELS_DIR / "old_models").is_dir() else 0
    return {"models": out, "archived": archived}


@_safe(lambda: {"ok": False, "error": "not found"})
def model_source(name) -> dict:
    """The .als source text + metadata for one model (for the inspector)."""
    try:
        name = _clean_model(name)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    f = _MODELS_DIR / f"{name}.als"
    if not f.exists():
        return {"ok": False, "error": f"no such model: {name}"}
    try:
        text = f.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"ok": False, "error": str(e)}
    meta = _als_meta(f)
    return {"ok": True, "name": name, "text": text, "path": str(f),
            "vscode": vscode_uri(str(f)), **meta}


# ══════════════════════════════════════════════════════════════════════════════
# 4e. catalog — generic source-of-truth file browser (configs / hooks / findings)
# ══════════════════════════════════════════════════════════════════════════════
def _catalog_entry(path: Path, base: Path) -> dict:
    rel = str(path.relative_to(base)) if base in path.parents or base == path.parent else path.name
    is_md = path.suffix == ".md"
    rec = {"name": rel, "path": str(path), "vscode": vscode_uri(str(path)),
           "is_markdown": is_md}
    try:
        if path.stat().st_size <= 300000:
            rec["text"] = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return rec


@_safe(lambda: {"ok": False, "builds": []})
def gem5_builds() -> dict:
    """The gem5-build registry (specs/gem5_builds.json) — one annotated entry per
    build + its timing-hook status. Source of truth for Utilities > gem5 builds."""
    p = _SPECS_DIR / "gem5_builds.json"
    if not p.exists():
        return {"ok": False, "error": f"missing {p}", "builds": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    data["ok"] = True
    data["_path"] = str(p)
    data["_vscode"] = vscode_uri(str(p))
    return data


@_safe(lambda: {"ok": False, "hooks": []})
def gem5_hooks_registry() -> dict:
    """The gem5-hook registry (specs/gem5_hooks.json) — every instrumentation /
    observation hook we've built + its purpose. Utilities > gem5 hooks (purposes)."""
    p = _SPECS_DIR / "gem5_hooks.json"
    if not p.exists():
        return {"ok": False, "error": f"missing {p}", "hooks": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    data["ok"] = True
    data["_path"] = str(p)
    data["_vscode"] = vscode_uri(str(p))
    return data


@_safe(lambda: {"ok": False, "models": []})
def alloy_models() -> dict:
    """Annotated Alloy-model table: the auto-parsed model_inventory (defense family,
    scope, transmitters, xml count) joined with curated specs/alloy_models.json
    (tier, summary, intention, caveat). Utilities > Alloy models."""
    inv = model_inventory()
    ann_path = _SPECS_DIR / "alloy_models.json"
    ann_doc = {}
    if ann_path.exists():
        try:
            ann_doc = json.loads(ann_path.read_text(encoding="utf-8"))
        except Exception:
            ann_doc = {}
    anns = ann_doc.get("annotations", {})
    _tier_order = {"production": 0, "variant": 1, "bugsynth": 2, "legacy": 3, "": 4}
    rows = []
    for m in inv.get("models", []):
        a = anns.get(m["name"], {})
        m = {**m, "tier": a.get("tier", ""), "summary": a.get("summary", ""),
             "intention": a.get("intention", ""), "caveat": a.get("caveat", ""),
             "aliases": a.get("aliases", "")}
        rows.append(m)
    rows.sort(key=lambda r: (_tier_order.get(r.get("tier", ""), 4), r["name"]))
    return {"ok": True, "models": rows, "archived": inv.get("archived", 0),
            "tiers": ann_doc.get("tiers", {}), "_vscode": vscode_uri(str(ann_path))}


@_safe(lambda: {"kind": None, "entries": []})
def catalog(kind) -> dict:
    """List + inline a canonical source-of-truth set. kind ∈ runconfigs|gem5hooks|findings."""
    entries = []
    if kind == "runconfigs":
        base = RUNCONFIGS
        files = sorted(base.glob("*.jsonc")) if base.is_dir() else []
    elif kind == "gem5hooks":
        base = ROOT / "gem5-hooks"
        files = sorted(p for p in base.rglob("*") if p.is_file()) if base.is_dir() else []
    elif kind == "findings":
        base = ROOT
        files = []
        for d in [ROOT / "wiki" / "findings", ROOT / "bugsynth"]:
            if d.is_dir():
                files += sorted(d.rglob("*.md"))
    else:
        return {"kind": kind, "entries": [], "error": f"unknown kind {kind!r}"}
    for p in files:
        entries.append(_catalog_entry(p, base))
    return {"kind": kind, "entries": entries}


# ══════════════════════════════════════════════════════════════════════════════
# 4f. hit categories (source of truth) + per-run detail (the gem5-card viewer)
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {"categories": {}})
def hit_categories() -> dict:
    """The central hit-category registry (specs/hit_categories.json)."""
    p = _SPECS_DIR / "hit_categories.json"
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d["_path"] = str(p)
            d["_vscode"] = vscode_uri(str(p))
            return d
        except Exception as e:
            return {"categories": {}, "error": str(e)}
    return {"categories": {}}


def _find_campaign(name):
    cd = _campaign_dirs().get(name)
    if cd is not None:
        return cd
    cand = RESULTS / name
    return cand if cand.is_dir() else None


@_safe(lambda: {"ok": False, "error": "not found"})
def run_detail(name) -> dict:
    """Everything the old run-monitor showed for one gem5 campaign + the categorized
    hit buckets (joined to the hit_categories registry). name = results_name."""
    cd = _find_campaign(name)
    if cd is None:
        return {"ok": False, "error": f"no campaign: {name}"}
    man = {}
    mp = cd / "manifest.json"
    if mp.exists():
        try:
            man = json.loads(mp.read_text())
        except Exception:
            man = {}
    variant, timing = None, {}
    cfgp = cd / "run_config.jsonc"
    if cfgp.exists():
        try:
            gem5 = _load_cfg(cfgp).get("gem5", {})
            variant = sm.variant_of(gem5)
            timing = {k: v for k, v in gem5.items()
                      if any(t in k for t in ("stall", "delay", "scheme", "branch_ann", "binary", "config_script"))}
        except Exception:
            pass
    modes = _campaign_modes(cd)   # [{mode, kinds:[{kind,total,hits}]}]
    # Bespoke flat layouts (e.g. CleanupSpec residue): no per-mode dirs, just
    # window-results*.json at the root — surface each as a pseudo-mode so the box
    # isn't empty. Hit = outcome mentioning RESIDUE/forbidden/leak/issued_in_window.
    if not modes:
        for f in sorted(cd.glob("window-results*.json")):
            try:
                recs = json.loads(f.read_text())
                recs = recs if isinstance(recs, list) else list(recs.values())
            except Exception:
                continue
            from collections import Counter as _C
            oc = _C((r.get("outcome") or r.get("status") or "?")
                    for r in recs if isinstance(r, dict))
            hits = sum(n for o, n in oc.items()
                       if any(t in str(o).lower() for t in
                              ("residue", "forbidden", "leak", "issued_in_window")))
            modes.append({"mode": f.stem, "kinds": [
                {"kind": o, "total": n, "hits": (n if any(t in str(o).lower() for t in
                 ("residue", "forbidden", "leak", "issued_in_window")) else 0)}
                for o, n in sorted(oc.items())]})
    tot_hits = sum(k.get("hits", 0) for m in modes for k in m.get("kinds", []))
    tot_recs = sum(k.get("total", 0) for m in modes for k in m.get("kinds", []))

    reg = hit_categories().get("categories", {})
    buckets = []
    bsum = cd / "diagnostics" / "buckets" / "summary.json"
    if bsum.exists():
        try:
            counts = json.loads(bsum.read_text())
            for cat, n in counts.items():
                meta = reg.get(cat, {})
                buckets.append({"category": cat, "count": n,
                                "label": meta.get("label", cat),
                                "verdict": meta.get("verdict", "?"),
                                "description": meta.get("description"),
                                "bug_md": meta.get("bug_md")})
            buckets.sort(key=lambda b: (-b["count"]))
        except Exception:
            pass
    return {"ok": True, "results_name": name, "campaign": cd.name,
            "model": man.get("model"), "gem5_binary": man.get("gem5_binary"),
            "variant": variant, "timing": timing, "started_at": man.get("started_at"),
            "total_records": tot_recs, "total_hits": tot_hits,
            "modes": modes, "buckets": buckets,
            "has_diagnostics": (cd / "diagnostics").is_dir()}


@_safe(lambda: {"ok": False, "stems": []})
def run_hit_stems(name, bucket=None, mode=None, limit=500) -> dict:
    """Stems in one bucket for a campaign (drill-in). Reads
    diagnostics/buckets/<mode>/<bucket>.txt, else <mode>/<kind>/window-hits.txt."""
    cd = _find_campaign(name)
    if cd is None:
        return {"ok": False, "error": f"no campaign: {name}", "stems": []}
    pairs, src = [], None   # each: {"stem", "mode"} — mode lets the UI fetch the program
    bdir = cd / "diagnostics" / "buckets"
    if bucket and bdir.is_dir():
        for f in bdir.rglob(f"{bucket}.txt"):
            if mode and f.parent.name != mode:
                continue
            src = str(f)
            fmode = f.parent.name
            try:
                for s in f.read_text().splitlines():
                    if s.strip():
                        pairs.append({"stem": s.strip(), "mode": fmode})
            except OSError:
                pass
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 500
    pairs.sort(key=lambda p: p["stem"])
    return {"ok": True, "bucket": bucket, "source": src,
            "total": len(pairs), "stems": pairs[:limit]}


_TIMELINE_TICKS = ["lc_retire", "xmit_issue", "xmit_signal", "xmit_execute",
                   "memaccess_tick", "cache_fill_tick", "xmit_complete",
                   "load_squash_tick", "xmit_retire", "fnc_retire"]


@_safe(lambda: {"ok": False, "events": []})
def hit_timeline(name, mode, stem) -> dict:
    """The saved pipeline-timing ticks for one hit → a timeline of events, each
    flagged in/out of the speculative window (lc_retire, fnc_retire). Feeds the
    'pipeline timeline' viz (the violating event is the in-window one). No re-run:
    these ticks are what the checker persisted in window-results.json."""
    cd = _find_campaign(name)
    if cd is None:
        return {"ok": False, "error": f"no campaign: {name}", "events": []}
    rec = None
    cands = []
    if mode:
        cands += list(cd.glob(f"{mode}/window-results.json")) + list(cd.glob(f"{mode}/*/window-results.json"))
    cands += (list(cd.glob("*/window-results.json")) + list(cd.glob("*/*/window-results.json"))
              + list(cd.glob("window-results*.json")))
    for f in cands:
        try:
            recs = json.loads(f.read_text())
            recs = recs if isinstance(recs, list) else list(recs.values())
        except Exception:
            continue
        for r in recs:
            if isinstance(r, dict) and r.get("name") == stem:
                rec = r
                break
        if rec:
            break
    if rec is None:
        return {"ok": False, "error": f"no record for {stem}", "events": []}
    lc, fnc = rec.get("lc_retire"), rec.get("fnc_retire")

    def _inwin(t):
        return (isinstance(lc, (int, float)) and isinstance(fnc, (int, float))
                and isinstance(t, (int, float)) and lc < t < fnc)

    events = []
    for k in _TIMELINE_TICKS:
        v = rec.get(k)
        if isinstance(v, (int, float)):
            events.append({"label": k, "tick": v, "in_window": _inwin(v)})
    for k in ("l1_eviction_ticks", "l2_eviction_ticks"):
        for t in (rec.get(k) or []):
            if isinstance(t, (int, float)):
                events.append({"label": k.replace("_ticks", ""), "tick": t, "in_window": _inwin(t)})
    events.sort(key=lambda e: e["tick"])
    return {"ok": True, "name": stem, "mode": mode, "outcome": rec.get("outcome"),
            "xmit_kind": rec.get("xmit_kind"), "xmit_pc": rec.get("xmit_pc"),
            "window": {"lc_retire": lc, "fnc_retire": fnc},
            "events": events, "record": rec}


# ══════════════════════════════════════════════════════════════════════════════
# 4g. defense units (defense × implementation) + transmitter criteria
# ══════════════════════════════════════════════════════════════════════════════
def _read_spec(relpath):
    f = _SPECS_DIR / relpath
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


@_safe(lambda: {"units": []})
def defense_units() -> dict:
    """The defense_units.json registry, each unit enriched with its criteria specs
    (leakage/timing/fanout contents) + whether its results campaigns exist on disk."""
    d = _read_spec("defense_units.json")
    if d is None:
        return {"units": []}
    camp = set(_campaign_dirs().keys())
    for u in d.get("units", []):
        u["leakage_spec"] = _read_spec(f"leakage/{u.get('leakage')}") if u.get("leakage") and not str(u.get("leakage")).startswith("NEEDS") else None
        u["timing_spec"] = _read_spec(f"timing/{u.get('timing')}") if u.get("timing") and not str(u.get("timing")).startswith("NEEDS") else None
        u["fanout_spec"] = _read_spec(f"fanout/{u.get('fanout')}") if u.get("fanout") and not str(u.get("fanout")).startswith("NEEDS") else None
        present = []
        for r in u.get("results", []):
            base = r.replace("__latest", "")
            if base in camp or (RESULTS / r).exists():
                present.append(r)
        u["results_present"] = present
    d["_vscode"] = vscode_uri(str(_SPECS_DIR / "defense_units.json"))
    return d


def _strip_asm_boilerplate(text: str):
    """Return (body_lines, n_stripped). Strips the CONTIGUOUS prologue (assembler
    directives, function label, frame setup pushq/movq-rbp/andq/subq, and the
    stack zero-init `movq $0, N(%rsp)` run) from the top and the CONTIGUOUS
    epilogue (frame teardown popq/leave/ret + trailing directives) from the
    bottom — leaving only the concretized litmus body. Contiguous-only so a real
    body instruction is never removed."""
    import re as _re
    lines = text.splitlines()
    pro = (_re.compile(r'^\s*(\.|#|"[^"]+":)')                        # directive / comment / label
           , _re.compile(r'^\s*(pushq\b|movq\s+%rsp,\s*%rbp|movq\s+%rbp,\s*%rsp'
                         r'|andq\s+\$-?\d+,\s*%rsp|subq\s+\$\d+,\s*%rsp'
                         r'|movq\s+\$0,\s*\d+\(%rsp\))'))
    epi = (_re.compile(r'^\s*(\.|#)')                                 # trailing directives/comments
           , _re.compile(r'^\s*(popq|leaveq|leave|retq|ret|addq\s+\$\d+,\s*%rsp|movq\s+%rbp,\s*%rsp)\b'))
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s == "" or pro[0].match(lines[i]) or pro[1].match(lines[i]):
            i += 1
        else:
            break
    j = n - 1
    while j >= i:
        s = lines[j].strip()
        if s == "" or epi[0].match(lines[j]) or epi[1].match(lines[j]):
            j -= 1
        else:
            break
    body = [l for l in lines[i:j + 1] if l.strip()]
    return body, (n - len(body))


@_safe(lambda: {"ok": False, "text": ""})
def program_clean(model, mode, stem) -> dict:
    """The concretized .s BODY only (prologue/epilogue stripped) for a program."""
    ft = file_text(model, mode, stem, "s")
    if not ft.get("ok"):
        return {"ok": False, "error": ft.get("error", "no program"), "text": ""}
    body, stripped = _strip_asm_boilerplate(ft.get("text", ""))
    return {"ok": True, "model": model, "mode": mode, "stem": stem,
            "text": "\n".join(body), "lines": len(body), "stripped": stripped,
            "path": ft.get("path"), "vscode": ft.get("vscode")}


@_safe(lambda: {"ok": False, "stems": []})
def xml_instances(model, limit=50) -> dict:
    """First N XML-instance stems for a model (for the XML-card dropdown inspector)."""
    try:
        model = _clean_model(model)
    except ValueError as e:
        return {"ok": False, "error": str(e), "stems": []}
    try:
        limit = max(1, min(int(limit), 1000))
    except (TypeError, ValueError):
        limit = 50
    xd = TESTSETS / model / "xml"
    names = []
    if xd.is_dir():
        try:
            names = sorted(e.name[:-4] for e in _os.scandir(xd) if e.name.endswith(".xml"))
        except OSError:
            pass
    return {"ok": True, "model": model, "total": len(names), "stems": names[:limit]}


@_safe(lambda: {})
def transmitter_criteria() -> dict:
    """All the transmitter/leakage criteria work, bundled for the Annotation/Check
    utility: the per-kind leak gate + the stage mapping + per-defense transmitter sets."""
    out = {}
    tc = _read_spec("transmitter_criteria.json")
    if tc is not None:
        out["criteria"] = tc
    sm_map = _read_spec("transmitter_stage_mapping.json")
    if sm_map is not None:
        out["stage_mapping"] = sm_map
    leak = {}
    ld = _SPECS_DIR / "leakage"
    if ld.is_dir():
        for f in sorted(ld.glob("*.json")):
            v = _read_spec(f"leakage/{f.name}")
            if v is not None:
                leak[f.stem] = v
    out["leakage"] = leak
    out["_vscode"] = vscode_uri(str(_SPECS_DIR / "transmitter_criteria.json"))
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 5. corpus
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {"model": None, "modes": [], "xml": 0})
def corpus(model, mode=None, offset=0, limit=200) -> dict:
    model_dir = TESTSETS / _clean_model(model)
    if mode is None:
        return {
            "model": model,
            "modes": [_mode_counts(model_dir, m) for m in _list_modes(model_dir)],
            "xml": _count(model_dir / "xml", ".xml"),
        }

    mode = _clean_component(mode)
    ann_dir = model_dir / mode / "ann"
    stems = []
    try:
        for f in ann_dir.glob("*.ann.json"):
            stems.append(f.name[: -len(".ann.json")])
    except OSError:
        pass
    stems.sort()
    total = len(stems)
    try:
        offset = max(0, int(offset))
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        offset, limit = 0, 200
    page = stems[offset: offset + limit]

    tests = []
    for stem in page:  # kind reads capped to the page (<= limit)
        kind = _ann_xmit_kind(ann_dir / f"{stem}.ann.json")
        tests.append({"stem": stem, "kind": kind})

    return {
        "model": model,
        "mode": mode,
        "total": total,
        "offset": offset,
        "limit": limit,
        "tests": tests,
    }


def _ann_xmit_kind(path: Path):
    try:
        d = json.loads(path.read_text())
        return (d.get("xmit") or {}).get("kind")
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 6. test_features
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {"model": None, "mode": None, "stem": None, "kind": None,
                "checker": {"name": None, "criterion": None},
                "ann": {}, "has": {"xml": False, "ll": False, "s": False,
                                   "ann": False}})
def test_features(model, mode, stem) -> dict:
    model = _clean_model(model)
    mode = _clean_component(mode)
    stem = _clean_stem(stem)
    model_dir = TESTSETS / model
    ann_path = model_dir / mode / "ann" / f"{stem}.ann.json"

    ann = {}
    try:
        if ann_path.exists():
            ann = json.loads(ann_path.read_text())
    except Exception:
        ann = {}

    kind = (ann.get("xmit") or {}).get("kind")
    has = {
        "xml": (model_dir / "xml" / f"{stem}.xml").exists(),
        "ll": (model_dir / mode / "llvm" / f"{stem}.ll").exists(),
        "s": (model_dir / mode / "asm" / f"{stem}.s").exists(),
        "ann": ann_path.exists(),
    }
    return {
        "model": model,
        "mode": mode,
        "stem": stem,
        "kind": kind,
        "checker": checker_for_kind(kind),
        "ann": ann,
        "has": has,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. file_text
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {"ok": False, "text": "", "path": None, "error": "internal error"})
def file_text(model, mode, stem, kind) -> dict:
    try:
        model = _clean_model(model)
        stem = _clean_stem(stem)
    except ValueError as e:
        return {"ok": False, "text": "", "path": None, "error": str(e)}

    model_dir = TESTSETS / model
    if kind == "xml":
        path = model_dir / "xml" / f"{stem}.xml"
    else:
        try:
            mode = _clean_component(mode)
        except ValueError as e:
            return {"ok": False, "text": "", "path": None, "error": str(e)}
        sub = {"ll": ("llvm", ".ll"),
               "s": ("asm", ".s"),
               "ann": ("ann", ".ann.json")}.get(kind)
        if sub is None:
            return {"ok": False, "text": "", "path": None,
                    "error": f"unknown kind {kind!r}"}
        subdir, ext = sub
        path = model_dir / mode / subdir / f"{stem}{ext}"

    if not path.exists():
        return {"ok": False, "text": "", "path": str(path),
                "error": "file not found"}
    try:
        raw = path.read_bytes()[: _MAX_TEXT_BYTES]
        text = raw.decode("utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "text": "", "path": str(path), "error": str(e)}
    return {"ok": True, "text": text, "path": str(path)}


# ══════════════════════════════════════════════════════════════════════════════
# 8. instruction_tables
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {"kind_categories": {}, "instructions": {}, "by_kind": []})
def instruction_tables() -> dict:
    try:
        tbl = sm.load_jsonc(INSTRUCTION_TABLES)
    except Exception:
        tbl = {}
    kind_categories = tbl.get("kind_categories", {}) or {}
    instructions = tbl.get("instructions", {}) or {}

    by_kind = []
    for kind, category in kind_categories.items():
        cands = []
        for c in instructions.get(category, []) or []:
            cands.append({
                "name": c.get("name"),
                "llvm_op": c.get("llvm_op"),
                "uses": c.get("uses", []),
                "comment": c.get("comment"),
            })
        by_kind.append({
            "kind": kind,
            "category": category,
            "candidates": cands,
        })

    return {
        "kind_categories": kind_categories,
        "instructions": instructions,
        "by_kind": by_kind,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 9. checkers
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {})
def checkers() -> dict:
    return {kind: {"checker": v["checker"], "criterion": v["criterion"]}
            for kind, v in CHECKERS.items()}


# ══════════════════════════════════════════════════════════════════════════════
# 10. exec_graph  (STUB-level, but spo edges + node flags are real)
# ══════════════════════════════════════════════════════════════════════════════
def _parse_exec_graph(xml_path: Path) -> dict:
    """Parse a single Alloy-instance XML into {nodes, edges, note}.

    Reuses STAGE2 parsexml for the Alloy parser, topo-sort, and kind mapping so
    the pc assignment matches the compiler's canonical program order.
    """
    note = ("spo edges and node flags are real; rf/ddi edges are mapped from "
            "operand atoms to their owning instructions.")
    text = xml_path.read_text(encoding="utf-8")

    if _px is not None:
        inst = _px.parse_alloy_xml(text)
        sig_atoms = inst.sig_atoms
        fields = inst.fields
        atom_key = _px._atom_sort_key
        kind_token = _px._kind_token
        topo = _px.topo_sort
    else:  # pragma: no cover - fall back to a minimal inline parser
        root = ET.fromstring(text)
        sig_atoms = {}
        fields = {}
        for sig in root.iter("sig"):
            sig_atoms[sig.attrib.get("label", "")] = {
                a.attrib["label"] for a in sig.findall("atom")}
        for f in root.iter("field"):
            fields[f.attrib.get("label", "")] = [
                tuple(a.attrib["label"] for a in t.findall("atom"))
                for t in f.findall("tuple")]

        def atom_key(a):
            m = re.match(r"^(.*)\$(\d+)$", a)
            return (m.group(1), int(m.group(2)), a) if m else (a, -1, a)

        _T = {"TLoad": "ld", "TStore": "str", "TBranchn": "br_n",
              "TBranchx": "br_x", "TOthern": "other_n", "TOtherx": "other_x"}

        def kind_token(ins, kind_of):
            tag = kind_of.get(ins, "")
            base = tag.split("$")[0] if "$" in tag else tag
            return _T.get(base, "unknown")

        def topo(nodes, edges):
            # Simple Kahn topo-sort (pop from end, matching parsexml order).
            adj = {n: [] for n in nodes}
            indeg = {n: 0 for n in nodes}
            for a, b in edges:
                adj.setdefault(a, []).append(b)
                indeg.setdefault(b, 0)
                indeg.setdefault(a, 0)
                indeg[b] += 1
            q = [n for n in nodes if indeg.get(n, 0) == 0]
            out = []
            while q:
                n = q.pop()
                out.append(n)
                for m in adj.get(n, []):
                    indeg[m] -= 1
                    if indeg[m] == 0:
                        q.append(m)
            return out

    instr_atoms = sig_atoms.get("this/Instruction", set())
    kind_of = {ins: tag for ins, tag in fields.get("kind", [])}
    nodes = sorted(instr_atoms, key=atom_key)
    spo_edges = [(a, b) for (a, b) in fields.get("spo", [])
                 if a in instr_atoms and b in instr_atoms]
    try:
        order = topo(nodes, spo_edges)
    except Exception:
        order = nodes  # non-DAG / incomplete → stable fallback order

    pc_of = {ins: pc for pc, ins in enumerate(order)}
    resolved = {ins for (ins, _) in fields.get("isresolved", [])}
    committed = {ins for (ins, _) in fields.get("iscommitted", [])}
    xm = {ins for (ins, _) in fields.get("isxm", [])}

    out_nodes = []
    for ins in order:
        out_nodes.append({
            "id": pc_of[ins],
            "pc": pc_of[ins],
            "kind": kind_token(ins, kind_of),
            "isxm": ins in xm,
            "committed": ins in committed,
            "resolved": ins in resolved,
        })

    edges = []
    # spo: predecessor -> successor in program order. spo tuples are
    # (successor, predecessor); emit as src=predecessor pc, dst=successor pc.
    for succ, pred in spo_edges:
        if succ in pc_of and pred in pc_of:
            edges.append({"type": "spo", "src": pc_of[pred], "dst": pc_of[succ]})

    # Map operand atoms -> owning instruction pc, via the operand fields.
    op_owner = {}
    for fld in ("inreg", "inaddr", "inmem", "outreg", "outmem"):
        for tup in fields.get(fld, []):
            if len(tup) >= 2:
                owner, op = tup[0], tup[1]
                if owner in pc_of:
                    op_owner[op] = pc_of[owner]

    mapped_all = True
    for etype in ("rf", "ddi"):
        for tup in fields.get(etype, []):
            if len(tup) < 2:
                continue
            a, b = tup[0], tup[1]
            sa, da = op_owner.get(a), op_owner.get(b)
            if sa is None or da is None:
                mapped_all = False
                # Fall back to operand-atom-level edge, flagged in the note.
                edges.append({"type": etype, "src": a, "dst": b})
            else:
                edges.append({"type": etype, "src": sa, "dst": da})

    if not mapped_all:
        note += (" NOTE: some rf/ddi operands could not be mapped to an "
                 "instruction; those edges are at the operand-atom level (STUB).")

    return {"nodes": out_nodes, "edges": edges, "note": note}


@_safe(lambda: {"nodes": [], "edges": [], "note": "parse failed"})
def exec_graph(model, stem) -> dict:
    model = _clean_model(model)
    stem = _clean_stem(stem)
    xml_path = TESTSETS / model / "xml" / f"{stem}.xml"
    if not xml_path.exists():
        return {"nodes": [], "edges": [],
                "note": f"xml not found: {xml_path}"}
    return _parse_exec_graph(xml_path)


# ══════════════════════════════════════════════════════════════════════════════
# 11. launch_fanout
# ══════════════════════════════════════════════════════════════════════════════
@_safe(lambda: {"ok": False, "job_id": None, "log": None,
                "error": "internal error"})
def launch_fanout(model, config) -> dict:
    # Validate model: no path separators, must map to MODELS_DIR/<model>.als.
    if not isinstance(model, str) or not _MODEL_RE.match(model):
        return {"ok": False, "job_id": None, "log": None,
                "error": f"invalid model name: {model!r}"}
    model_file = MODELS_DIR / f"{model}.als"
    if not model_file.exists():
        return {"ok": False, "job_id": None, "log": None,
                "error": f"model file not found: {model_file}"}

    # Validate config: a file under RUNCONFIGS, or an existing path inside ROOT.
    if not isinstance(config, str) or not config:
        return {"ok": False, "job_id": None, "log": None,
                "error": "config is required"}
    cfg_path = Path(config)
    if not cfg_path.is_absolute():
        cfg_path = (RUNCONFIGS / config) if not cfg_path.exists() else cfg_path.resolve()
    cfg_path = cfg_path.resolve()
    try:
        root_resolved = ROOT.resolve()
        inside = cfg_path.is_relative_to(root_resolved)
    except AttributeError:  # Python < 3.9
        inside = str(cfg_path).startswith(str(ROOT.resolve()))
    if not cfg_path.exists() or not cfg_path.is_file():
        return {"ok": False, "job_id": None, "log": None,
                "error": f"config not found: {config}"}
    if not inside:
        return {"ok": False, "job_id": None, "log": None,
                "error": "config path is outside the repository"}

    # Launch testsetgen.py detached, redirecting output to a log file.
    JOBS_LOGS.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = JOBS_LOGS / f"gen-{model}-{ts}.log"
    try:
        logf = open(log_path, "w", encoding="utf-8")
        subprocess.Popen(
            ["python3", "testsetgen.py", "--model", model,
             "--config", str(cfg_path)],
            cwd=str(ROOT),
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception as e:
        return {"ok": False, "job_id": None, "log": str(log_path),
                "error": str(e)}

    # testsetgen records its own manifest entry; we don't return a job_id.
    return {"ok": True, "job_id": None, "log": str(log_path), "error": None}


def launch_run(model, config) -> dict:
    """Run-on-build: launch testrun.py (the gem5 consumer) detached on a testset
    against a run config. Same validation as launch_fanout. The config carries the
    build/scheme/timing (incl. sweep); for a sweep, point at a run config whose
    `sweep.enabled` is true (a synthesized one is fine)."""
    if not isinstance(model, str) or not _MODEL_RE.match(model):
        return {"ok": False, "log": None, "error": f"invalid model name: {model!r}"}
    model_file = MODELS_DIR / f"{model}.als"
    if not model_file.exists():
        return {"ok": False, "log": None, "error": f"model file not found: {model_file}"}
    if not isinstance(config, str) or not config:
        return {"ok": False, "log": None, "error": "config is required"}
    cfg_path = Path(config)
    if not cfg_path.is_absolute():
        cfg_path = (RUNCONFIGS / config) if not cfg_path.exists() else cfg_path.resolve()
    cfg_path = cfg_path.resolve()
    try:
        inside = cfg_path.is_relative_to(ROOT.resolve())
    except AttributeError:
        inside = str(cfg_path).startswith(str(ROOT.resolve()))
    if not cfg_path.exists() or not cfg_path.is_file():
        return {"ok": False, "log": None, "error": f"config not found: {config}"}
    if not inside:
        return {"ok": False, "log": None, "error": "config path is outside the repository"}

    JOBS_LOGS.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = JOBS_LOGS / f"run-{model}-{ts}.log"
    try:
        logf = open(log_path, "w", encoding="utf-8")
        subprocess.Popen(
            ["python3", "testrun.py", "--model", model, "--config", str(cfg_path)],
            cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT, start_new_session=True,
        )
    except Exception as e:
        return {"ok": False, "log": str(log_path), "error": str(e)}
    return {"ok": True, "log": str(log_path), "error": None}


# ── Input sanitizers ──────────────────────────────────────────────────────────
def _clean_model(model) -> str:
    if not isinstance(model, str) or not _MODEL_RE.match(model):
        raise ValueError(f"invalid model name: {model!r}")
    return model


def _clean_component(name) -> str:
    """A single path component (mode) — no separators, no traversal."""
    if (not isinstance(name, str) or not name
            or "/" in name or "\\" in name or name in (".", "..")):
        raise ValueError(f"invalid path component: {name!r}")
    return name


def _clean_stem(stem) -> str:
    if not isinstance(stem, str) or not _STEM_RE.match(stem):
        raise ValueError(f"invalid test stem: {stem!r}")
    return stem


# ══════════════════════════════════════════════════════════════════════════════
# Selftest
# ══════════════════════════════════════════════════════════════════════════════
def _selftest() -> int:
    """Call each function once and print a one-line shape summary. Must run
    cleanly on a machine with no testsets/ or results/ yet."""
    failures = 0

    def check(label, fn, *args, **kwargs):
        nonlocal failures
        try:
            r = fn(*args, **kwargs)
            summary = _shape(r)
            print(f"OK   {label:<28} {summary}")
            return r
        except Exception:
            failures += 1
            print(f"FAIL {label:<28}")
            traceback.print_exc()
            return None

    check("overview", overview)
    check("generation", generation)
    check("fanout", fanout)
    check("corpora", corpora)
    check("corpus(no mode)", corpus, "SPT_6")
    check("corpus(mode)", corpus, "SPT_6", "mispredict_not_taken")
    check("test_features", test_features, "SPT_6", "mispredict_not_taken",
          "inst-000001")
    check("file_text(missing)", file_text, "SPT_6", "mispredict_not_taken",
          "inst-000001", "ll")
    check("file_text(traversal)", file_text, "SPT_6", "x", "../../etc/passwd",
          "ll")
    check("instruction_tables", instruction_tables)
    check("checkers", checkers)
    check("exec_graph(missing)", exec_graph, "SPT_6", "inst-000001")
    # launch_fanout: exercise validation-only paths (these reject before spawn).
    r = check("launch_fanout(bad model)", launch_fanout, "../evil", "x.jsonc")
    assert r and r["ok"] is False, "bad model must be rejected"
    r = check("launch_fanout(no model file)", launch_fanout, "nonexistent_model",
              "run_config_smoke.jsonc")
    assert r and r["ok"] is False, "missing model file must be rejected"

    # Exercise annotation + checker parsing against the committed bug examples.
    print("-- annotation/checker parsing (bug examples) --")
    for bug in ("wiki/findings/bug/stt_slowcomm_vp_squash_race/inst-047231.ann.json",
                "wiki/findings/bug/recon_SLF_stlf_bypass/inst-014912.ann.json"):
        p = ROOT / bug
        if not p.exists():
            print(f"skip {bug} (not present)")
            continue
        try:
            ann = json.loads(p.read_text())
            kind = (ann.get("xmit") or {}).get("kind")
            ck = checker_for_kind(kind)
            assert ck["name"] and ck["criterion"]
            print(f"OK   ann parse {p.name:<24} kind={kind} "
                  f"checker={ck['name']} branches={len(ann.get('annotations', []))}")
        except Exception:
            failures += 1
            print(f"FAIL ann parse {p.name}")
            traceback.print_exc()

    # Exercise exec_graph parsing against the committed bug XML.
    print("-- exec_graph parsing (bug XML) --")
    for bug in ("wiki/findings/bug/stt_slowcomm_vp_squash_race/inst-047231.xml",
                "wiki/findings/bug/recon_SLF_stlf_bypass/inst-014912.xml"):
        p = ROOT / bug
        if not p.exists():
            print(f"skip {bug} (not present)")
            continue
        try:
            g = _parse_exec_graph(p)
            kinds = [n["kind"] for n in g["nodes"]]
            spo = sum(1 for e in g["edges"] if e["type"] == "spo")
            rf = sum(1 for e in g["edges"] if e["type"] == "rf")
            ddi = sum(1 for e in g["edges"] if e["type"] == "ddi")
            assert g["nodes"], "expected nodes"
            print(f"OK   graph {p.name:<24} nodes={len(g['nodes'])} "
                  f"spo={spo} rf={rf} ddi={ddi} kinds={kinds}")
        except Exception:
            failures += 1
            print(f"FAIL graph {p.name}")
            traceback.print_exc()

    print()
    if failures:
        print(f"SELFTEST FAILED: {failures} failure(s)")
    else:
        print("SELFTEST PASSED: all functions returned cleanly")
    return 1 if failures else 0


def _shape(obj) -> str:
    """Compact one-line description of a JSON-able result for the selftest."""
    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            if isinstance(v, (list, dict)):
                parts.append(f"{k}={_len(v)}")
            else:
                parts.append(f"{k}={v!r}" if not isinstance(v, str) or len(v) < 20
                             else f"{k}=<str>")
        return "{" + ", ".join(parts) + "}"
    if isinstance(obj, list):
        return f"list[{len(obj)}]"
    return repr(obj)


def _len(v):
    if isinstance(v, list):
        return f"[{len(v)}]"
    if isinstance(v, dict):
        return "{" + str(len(v)) + "}"
    return v


if __name__ == "__main__":
    sys.exit(_selftest())
