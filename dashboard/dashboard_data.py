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
