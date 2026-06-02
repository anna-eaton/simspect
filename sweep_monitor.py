#!/usr/bin/env python3
"""
sweep_monitor.py — live terminal dashboard for running SimSpect sweeps.

Refreshes every minute (--interval) and prints one section per running sweep:
a pipeline.py build (xml→llvm→asm→gem5) or a _sweep_watcher.py gem5 consumer.
Each section shows the testset, the stage it's in, a progress bar, and the key
config it's using for that build.

When a sweep's hit count goes up it rings the terminal bell and prints a red
alert banner naming the sweep/mode and the new count. It does not run anything.

    python3 sweep_monitor.py                 # refresh every 60s
    python3 sweep_monitor.py --interval 30   # faster refresh
    python3 sweep_monitor.py --once          # draw once and exit

Runs fine over SSH / in the VS Code integrated terminal (plain ANSI, no curses).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    _PT = ZoneInfo("America/Los_Angeles")
except Exception:  # no IANA tzdata in this image → manual rule below
    _PT = None


def _nth_sunday(year: int, month: int, n: int) -> int:
    """Day-of-month of the nth Sunday of (year, month)."""
    w = datetime(year, month, 1).weekday()        # Mon=0 … Sun=6
    first_sun = 1 + (6 - w) % 7
    return first_sun + (n - 1) * 7


def now_pt() -> str:
    if _PT is not None:
        return datetime.now(_PT).strftime("%Y-%m-%d %H:%M:%S %Z")
    # US Pacific without tzdata: PDT (2nd Sun Mar 02:00 → 1st Sun Nov 02:00), else PST.
    utc = datetime.now(timezone.utc)
    y = utc.year
    dst_start = datetime(y, 3, _nth_sunday(y, 3, 2), 10, tzinfo=timezone.utc)
    dst_end = datetime(y, 11, _nth_sunday(y, 11, 1), 9, tzinfo=timezone.utc)
    is_dst = dst_start <= utc < dst_end
    off, name = (-7, "PDT") if is_dst else (-8, "PST")
    return (utc + timedelta(hours=off)).strftime("%Y-%m-%d %H:%M:%S ") + name

ROOT = Path(__file__).parent.resolve()

# ── ANSI ──────────────────────────────────────────────────────────────────────
C = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "red": "\033[31m", "grn": "\033[32m", "yel": "\033[33m",
    "blu": "\033[34m", "mag": "\033[35m", "cyn": "\033[36m",
    "bgred": "\033[41m", "bgrn": "\033[42m",
}
BELL = "\a"


def c(s: str, *names: str) -> str:
    return "".join(C[n] for n in names) + s + C["reset"]


# ── jsonc + counting ────────────────────────────────────────────────────────
def load_jsonc(p: Path) -> dict:
    txt = p.read_text(encoding="utf-8")
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    txt = re.sub(r"//[^\n]*", "", txt)
    return json.loads(txt)


def count_suffix(d: Path, suffix: str) -> int:
    if not d.is_dir():
        return 0
    n = 0
    with os.scandir(d) as it:
        for e in it:
            if e.name.endswith(suffix):
                n += 1
    return n


def json_len(p: Path) -> int:
    try:
        return len(json.loads(p.read_text()))
    except Exception:
        return 0


def resolve(v: str) -> Path:
    p = Path(v)
    return p if p.is_absolute() else (ROOT / p)


# ── process discovery ────────────────────────────────────────────────────────
PIPE_RE = re.compile(r"pipeline\.py\s+(\w+)\s+--model\s+(\S+)\s+--config\s+(\S+)")


def _flag(args: str, name: str) -> str | None:
    m = re.search(rf"--{name}\s+(\S+)", args)
    return m.group(1) if m else None


def ps_lines() -> list[tuple[str, str]]:
    out = subprocess.run(["ps", "-eo", "etime=,args="],
                         capture_output=True, text=True).stdout
    rows = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        et, _, args = ln.partition(" ")
        rows.append((et.strip(), args.strip()))
    return rows


def discover():
    """Return (builds, watchers).

    builds:   {(model, config): {"phases": set, "etime": str, "kind": str}}
              kind ∈ "pipeline" (pipeline.py) | "gen" (testsetgen.py producer).
    watchers: list of {"config", "model", "etime", "type"}
              type ∈ "testrun" (testrun.py, per-kind) | "sweep" (_sweep_watcher.py).
    """
    builds: dict = {}
    watch: dict = {}    # (type, model, cfg) → entry; dedupes timeout-wrappers,
    #                     rapid --once relaunches, and duplicate ps lines.

    def _add_watch(wtype, model, cfg, et):
        if not (model and cfg):
            return
        key = (wtype, model, cfg)
        w = watch.get(key)
        if w is None:
            watch[key] = {"config": cfg, "model": model, "etime": et,
                          "type": wtype}
        elif _etime_secs(et) > _etime_secs(w["etime"]):
            w["etime"] = et

    for et, args in ps_lines():
        # ── consumers (gem5-only, produce hits) ───────────────────────────────
        if "testrun.py" in args:
            _add_watch("testrun", _flag(args, "model"), _flag(args, "config"), et)
            continue
        if "_sweep_watcher.py" in args:
            _add_watch("sweep", _flag(args, "model"), _flag(args, "config"), et)
            continue
        # ── producer (testsetgen.py: concurrent xml+llvm+asm, no gem5) ─────────
        if "testsetgen.py" in args:
            model, cfg = _flag(args, "model"), _flag(args, "config")
            if model and cfg:
                key = (model, cfg)
                builds.setdefault(key, {"phases": {"xml", "llvm", "asm"},
                                        "etime": et, "kind": "gen"})
            continue
        # ── pipeline.py build (xml→…→gem5, possibly scoring) ───────────────────
        m = PIPE_RE.search(args)
        if m and "pipeline.py" in args:
            phase, model, cfg = m.groups()
            # Skip the per-batch gem5 runs spawned by a watcher/testrun.
            if "_pass_cfg" in cfg:
                continue
            key = (model, cfg)
            b = builds.setdefault(key, {"phases": set(), "etime": et,
                                        "kind": "pipeline"})
            b["phases"].add(phase)
            # keep the longest-running etime as the build's age
            if _etime_secs(et) > _etime_secs(b["etime"]):
                b["etime"] = et
    return builds, list(watch.values())


def _etime_secs(et: str) -> int:
    # [[DD-]HH:]MM:SS
    days = 0
    if "-" in et:
        d, et = et.split("-", 1)
        days = int(d)
    parts = [int(x) for x in et.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return days * 86400 + h * 3600 + m * 60 + s


# ── progress bar ─────────────────────────────────────────────────────────────
def bar(done: int, total: int, width: int = 34, color: str = "grn") -> str:
    if total <= 0:
        return c("·" * width, "dim") + c("  (?)", "dim")
    frac = min(1.0, done / total)
    fill = int(round(frac * width))
    b = c("█" * fill, color) + c("░" * (width - fill), "dim")
    pct = f"{frac * 100:5.1f}%"
    return f"{b} {pct} {c(f'{done}/{total}', 'dim')}"


# ── config summary ───────────────────────────────────────────────────────────
def _scheme2_name(binary: str) -> str:
    """Numeric scheme 2 means STT on the recon/stt builds but maps to a Fence
    in gem5-spt's se.py — disambiguate by the binary path."""
    b = (binary or "").lower()
    if "spt" in b:
        return "Fence"
    if "recon" in b or "stt" in b:
        return "STT"
    return "STT/Fence"


def variant_of(gem5: dict) -> str:
    extra = gem5.get("extra_args", []) or []
    sched = next((a.split("=", 1)[1] for a in extra
                  if a.startswith("--scheme=")), None)
    if sched:
        tag = sched
    else:
        scheme = gem5.get("scheme", 2)
        tag = {0: "Unsafe", 1: "Delay",
               2: _scheme2_name(gem5.get("binary", "")), 3: "DoM"}.get(
            scheme, str(scheme))
    flags = [a.lstrip("-") for a in extra if not a.startswith("--scheme=")]
    return tag + (("  " + " ".join(flags)) if flags else "")


def cfg_summary_lines(cfg: dict) -> list[str]:
    """Two dense lines: build/binary+variant, then runtime knobs."""
    g = cfg.get("gem5", {})
    sp = cfg.get("speculation", {})
    sw = cfg.get("sweep", {})
    binp = g.get("binary", "?")
    p = Path(binp).parts
    if binp != "?" and "build" in p:
        i = p.index("build")
        tree = p[i - 1] if i else binp
        isa = p[i + 1] if i + 1 < len(p) else ""
        binshort = f"{tree}:{isa}"
    else:
        binshort = Path(binp).name if binp != "?" else "?"

    l1 = c(binshort, "cyn") + c("  ·  ", "dim") + variant_of(g)

    bits = [f"jobs {g.get('jobs', '?')}",
            f"fnc {g.get('fnc_commit_stall_cycles', 0)}"]
    modes = [m.split("_", 1)[1] if m.startswith("mispredict_") else m
             for m in sp.get("branch_modes", [])]
    if modes:
        bits.append("modes " + ",".join(modes))
    if sw.get("enabled"):
        bits.append(f"sweep pts={sw.get('points')} "
                    f"unres={sw.get('unresolved_stall_cycles')}")
    l2 = c("  ·  ".join(bits), "dim")
    return [l1, l2]


# ── stage progress for a build ───────────────────────────────────────────────
STAGES = ["xml", "llvm", "asm", "gem5"]


def build_progress(model: str, cfg: dict, phases: set):
    """Return (xml_total, [(stage, mode, done, total, active)])."""
    testset_dir = resolve(cfg["paths"].get("testset_dir", "testsets"))
    results_dir = resolve(cfg["paths"].get("results_dir", "results"))
    results_name = cfg["paths"].get("results_name", model)
    ts = testset_dir / model
    rs = results_dir / results_name
    modes = cfg.get("speculation", {}).get("branch_modes", []) or [None]

    xml_total = count_suffix(ts / "xml", ".xml")
    if xml_total == 0:
        xml_total = int(cfg.get("alloy", {}).get("max_instances", 0))

    want = set(phases)
    if "all" in want:
        want = set(STAGES)

    rows = []
    # xml stage (shared across modes)
    if "xml" in want or "all" in phases:
        n = count_suffix(ts / "xml", ".xml")
        rows.append(("xml", None, n, xml_total or n, False))

    for mode in modes:
        base = ts if mode is None else ts / mode
        rbase = rs if mode is None else rs / mode
        if "llvm" in want:
            rows.append(("llvm", mode, count_suffix(base / "llvm", ".ll"),
                         xml_total, False))
        if "asm" in want:
            rows.append(("asm", mode, count_suffix(base / "asm", ".s"),
                         xml_total, False))
        if "gem5" in want:
            done = json_len(rbase / "window-results.json")
            tot = count_suffix(base / "asm", ".s") or xml_total
            rows.append(("gem5", mode, done, tot, False))

    # mark the first incomplete row as the "active" stage
    for i, (st, mode, done, tot, _) in enumerate(rows):
        if tot == 0 or done < tot:
            rows[i] = (st, mode, done, tot, True)
            break
    return xml_total, rows


def testrun_base(results_name: str) -> Path:
    """The live campaign dir for a testrun.py run: results/<name>__latest →
    results/<name>__<ts>. Falls back to the newest matching __<ts> dir."""
    latest = ROOT / "results" / f"{results_name}__latest"
    if latest.exists():
        return latest.resolve()
    cands = [d for d in (ROOT / "results").glob(f"{results_name}__*")
             if d.is_dir() and not d.is_symlink()]
    if cands:
        return max(cands, key=lambda d: d.stat().st_mtime)
    return ROOT / "results" / results_name      # not started yet


def testrun_progress(model: str, cfg: dict, base: Path):
    """Return list of (mode, done, ready, expected). 'done' sums across the
    per-kind window-results.json the testrun campaign partitions into."""
    testset_dir = resolve(cfg["paths"].get("testset_dir", "testsets"))
    ts = testset_dir / model
    modes = cfg.get("speculation", {}).get("branch_modes", []) or [None]
    expected = int(cfg.get("alloy", {}).get("max_instances", 0))
    rows = []
    for mode in modes:
        mdir = base if mode is None else base / mode
        done = sum(json_len(wr) for wr in mdir.glob("*/window-results.json")) \
            if mdir.is_dir() else 0
        ready = count_suffix((ts if mode is None else ts / mode) / "asm", ".s")
        rows.append((mode, done, ready, expected))
    return rows


def watcher_progress(model: str, cfg: dict):
    """Return list of (mode, done, ready, expected)."""
    testset_dir = resolve(cfg["paths"].get("testset_dir", "testsets"))
    results_name = cfg["paths"].get("results_name", model)
    ts = testset_dir / model
    rs = ROOT / "results" / results_name
    modes = cfg.get("speculation", {}).get("branch_modes", []) or [None]
    expected = int(cfg.get("alloy", {}).get("max_instances", 0))
    rows = []
    for mode in modes:
        base = ts if mode is None else ts / mode
        rbase = rs if mode is None else rs / mode
        ready = count_suffix(base / "asm", ".s")
        done = json_len(rbase / "window-results.json")
        rows.append((mode, done, ready, expected))
    return rows


# ── hits tracking ────────────────────────────────────────────────────────────
# Transmitter kinds, in display order. testrun.py partitions hits into
# <mode>/<kind>/window-hits.txt; older layouts keep a single <mode>/window-hits.txt
# (recorded under kind None).
KIND_ORDER = {"ld": 0, "br_x": 1, "other_x": 2}


def _count_hits_file(f: Path) -> int:
    try:
        return sum(1 for ln in f.read_text().splitlines() if ln.strip())
    except Exception:
        return 0


def scan_kind_hits(base: Path, modes: list) -> dict:
    """Return {(mode, kind): count}. kind is the per-transmitter bucket when the
    layout partitions (testrun.py: <mode>/<kind>/window-hits.txt), else None
    (watcher/build: <mode>/window-hits.txt)."""
    out: dict = {}
    for mode in modes:
        mdir = base if mode is None else base / mode
        if not mdir.is_dir():
            continue
        kind_files = sorted(p for p in mdir.glob("*/window-hits.txt"))
        if kind_files:
            for f in kind_files:
                out[(mode, f.parent.name)] = _count_hits_file(f)
        else:
            f = mdir / "window-hits.txt"
            if f.exists():
                out[(mode, None)] = _count_hits_file(f)
    return out


def gather_hit_stems(base: Path, modes: list) -> list:
    """Union of hit stems (issued_in_window) across all modes/kinds, for triage."""
    stems: set = set()
    for mode in modes:
        mdir = base if mode is None else base / mode
        if not mdir.is_dir():
            continue
        files = list(mdir.glob("*/window-hits.txt"))
        f = mdir / "window-hits.txt"
        if not files and f.exists():
            files = [f]
        for hf in files:
            try:
                stems |= {ln.strip() for ln in hf.read_text().splitlines()
                          if ln.strip()}
            except OSError:
                pass
    return sorted(stems)


# ── known-vs-new triage via per-results diagnostics/ scripts ──────────────────
# Each results dir carries diagnostics/diag_*.py exposing
# is_known(stem, xml_dir) -> (matched, reason). A hit is KNOWN if any script
# matches (attributed to an understood bug), else NEW (the research signal).
_DIAG_CACHE: dict = {}   # path -> (mtime, is_known_fn | None)
_VERDICT: dict = {}      # (path, mtime, stem) -> bool
_NEW_PREV: dict = {}     # results_name -> last 'new' (unattributed) hit count


def _load_diag_funcs(diag_dir: Path) -> list:
    """Return [(path, mtime, is_known_fn), ...] for diag_*.py, mtime-cached."""
    funcs = []
    if not diag_dir.is_dir():
        return funcs
    for f in sorted(diag_dir.glob("diag_*.py")):
        try:
            mt = f.stat().st_mtime
        except OSError:
            continue
        cached = _DIAG_CACHE.get(f)
        if cached is None or cached[0] != mt:
            fn = None
            try:
                modname = "simspect_diag_" + re.sub(r"\W", "_", str(f))
                spec = importlib.util.spec_from_file_location(modname, f)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                fn = getattr(mod, "is_known", None)
            except Exception:
                fn = None
            _DIAG_CACHE[f] = cached = (mt, fn)
        if cached[1] is not None:
            funcs.append((f, cached[0], cached[1]))
    return funcs


def triage_hits(stems: list, diag_funcs: list, xml_dir: Path):
    """Return (total, known, new, has_diag). Per-stem verdicts are cached."""
    if not diag_funcs:
        return (len(stems), 0, len(stems), False)
    known = 0
    for s in stems:
        hit_known = False
        for path, mt, fn in diag_funcs:
            key = (path, mt, s)
            v = _VERDICT.get(key)
            if v is None:
                try:
                    v = bool(fn(s, xml_dir)[0])
                except Exception:
                    v = False
                _VERDICT[key] = v
            if v:
                hit_known = True
                break
        known += hit_known
    return (len(stems), known, len(stems) - known, True)


def triage_line(results_name: str, base: Path, modes: list, model: str,
                cfg: dict, alerts: list) -> str:
    """The 'known K · new U' summary line for a section, or '' if no hits. Rings
    the alert ONLY when the 'new' (unattributed) count rises — known artifacts
    don't ping."""
    stems = gather_hit_stems(base, modes)
    if not stems:
        return ""
    funcs = _load_diag_funcs(base / "diagnostics")
    xml_dir = resolve(cfg["paths"].get("testset_dir", "testsets")) / model / "xml"
    total, known, new, has_diag = triage_hits(stems, funcs, xml_dir)

    prev = _NEW_PREV.get(results_name)
    _NEW_PREV[results_name] = new
    if prev is not None and new > prev:
        alerts.append(f"{results_name}: +{new - prev} NEW unexplained hit(s) "
                      f"({prev} → {new}) — review")

    if not has_diag:
        return "    " + c(f"triage  no diagnostics/ — {new} unattributed", "yel")
    kc = c(f"known {known}", "dim")
    nc = c(f"new {new}", "red", "bold") if new else c("new 0", "grn")
    return ("    " + c("triage  ", "bold") + f"{kc}  ·  {nc}  "
            + c(f"({len(funcs)} diag)", "dim"))


# ── render ───────────────────────────────────────────────────────────────────
def render(prev_hits: dict, stale_secs: int) -> tuple[str, dict, list]:
    builds, watchers = discover()
    out = []
    hits_now: dict = {}
    alerts: list = []

    hdr = c(f" SimSpect sweep monitor ", "bold", "cyn")
    out.append(hdr + c(f"  {now_pt()}", "dim"))
    out.append(c("─" * 72, "dim"))

    if not builds and not watchers:
        out.append(c("  no sweeps running (no pipeline.py / _sweep_watcher.py)", "yel"))

    active_names: set = set()   # result dirs being actively written right now

    # ── builds ────────────────────────────────────────────────────────────────
    for (model, cfgpath), info in sorted(builds.items()):
        cfg = _safe_cfg(cfgpath)
        results_name = cfg.get("paths", {}).get("results_name", model)
        phases = info["phases"]
        # a build only produces gem5 results (hits) when its phase set includes
        # gem5 (or 'all'); an asm-only build (or testsetgen producer) just feeds
        # a watcher.
        is_gen = info.get("kind") == "gen"
        scoring = (not is_gen) and ("gem5" in phases or "all" in phases)
        if scoring:
            active_names.add(results_name)
        ph = ("gen" if is_gen else
              "all" if "all" in phases else "+".join(sorted(phases)))
        sec = list(cfg_summary_lines(cfg))
        sec = ["    " + ln for ln in sec]
        try:
            _, rows = build_progress(model, cfg, phases)
        except Exception as e:
            sec.append(c(f"    progress error: {e}", "red"))
            rows = []
        prog_val = sum(done for _, _, done, _, _ in rows)
        has_work = any(tot > 0 and done < tot for _, _, done, tot, _ in rows)
        for st, mode, done, tot, active in rows:
            label = st if mode is None else f"{st} {c(mode, 'dim')}"
            marker = c("▶", "yel", "bold") if active else " "
            col = "yel" if active else "grn"
            sec.append(f"  {marker} {label:<28} {bar(done, tot, color=col)}")
        if scoring:
            modes = cfg.get("speculation", {}).get("branch_modes", []) or [None]
            base = resolve(cfg["paths"].get("results_dir", "results")) / results_name
            hrows = _scan_hits(results_name, base, modes, hits_now, prev_hits)
            sec.append("    " + _hits_line(hrows))
            tl = triage_line(results_name, base, modes, model, cfg, alerts)
            if tl:
                sec.append(tl)

        state, idle = freshness(("build", model, cfgpath), prog_val,
                                has_work, stale_secs)
        label = "GEN  " if is_gen else "BUILD"
        dest = ("testsets/" + model if is_gen else "results/" + results_name)
        title = (f"▌ {label}  {model}  → {dest}   [{ph}]  up {info['etime']}")
        _emit_section(out, "blu", title, sec, state, idle, alerts)

    # ── watchers ──────────────────────────────────────────────────────────────
    for w in watchers:
        cfg = _safe_cfg(w["config"])
        model = w["model"]
        results_name = cfg.get("paths", {}).get("results_name", model)
        is_testrun = w.get("type") == "testrun"
        modes = cfg.get("speculation", {}).get("branch_modes", []) or [None]
        active_names.add(results_name)
        if is_testrun:
            base = testrun_base(results_name)
            # campaign dir + its __latest symlink aren't the "completed" leftovers
            active_names.add(base.name)
            active_names.add(f"{results_name}__latest")
            dest = f"results/{base.name}"
        else:
            base = ROOT / "results" / results_name
            dest = f"results/{results_name}"
        sec = ["    " + ln for ln in cfg_summary_lines(cfg)]
        try:
            rows = (testrun_progress(model, cfg, base) if is_testrun
                    else watcher_progress(model, cfg))
        except Exception as e:
            sec.append(c(f"    progress error: {e}", "red"))
            rows = []
        prog_val = sum(done for _, done, _, _ in rows)
        # work is available only when there is compiled-but-unscored backlog
        has_work = any(ready > done for _, done, ready, _ in rows)
        for mode, done, ready, expected in rows:
            label = "gem5" if mode is None else f"gem5 {c(mode, 'dim')}"
            sec.append(f"    {label:<28} {bar(done, ready, color='mag')}"
                       + (c(f"  ready {ready}/{expected}", "dim")
                          if expected else ""))
        hrows = _scan_hits(results_name, base, modes, hits_now, prev_hits)
        sec.append("    " + _hits_line(hrows))
        tl = triage_line(results_name, base, modes, model, cfg, alerts)
        if tl:
            sec.append(tl)

        state, idle = freshness(("watch", results_name), prog_val,
                                has_work, stale_secs)
        wlabel = "TESTRUN" if is_testrun else "WATCH  "
        title = (f"▌ {wlabel}  {model}  → {dest}   [gem5·by-kind]  "
                 f"up {w['etime']}")
        _emit_section(out, "mag", title, sec, state, idle, alerts)

    # ── completed / idle result dirs (not actively written) ────────────────────
    idle = list_idle_results(active_names)
    if idle:
        out.append("")
        out.append(c("▌ COMPLETED / IDLE  (no live process writing these)",
                     "bold", "dim"))
        cells = [_idle_cell(*e) for e in idle]
        for i in range(0, len(cells), 2):
            out.append("    " + "    ".join(cells[i:i + 2]))

    # ── hit alert banner ──────────────────────────────────────────────────────
    if alerts:
        out.insert(2, "")
        for a in reversed(alerts):
            out.insert(3, c(f"  🔔  {a}", "bold", "bgred"))

    total_hits = sum(hits_now.values())
    out.append("")
    out.append(c("─" * 72, "dim"))
    out.append(c(f"  live hits across running sweeps: {total_hits}", "bold",
                 "grn" if total_hits else "dim") +
               c("    Ctrl-C to quit", "dim"))
    return "\n".join(out), hits_now, alerts


def _idle_cell(name: str, hits: int, tests: int, mtime: float) -> str:
    """One compact, fixed-width cell for the two-per-row idle grid."""
    nm = c(f"{name:<30}", "dim")
    h = f"{hits:>5}"
    hc = c(h, "grn") if hits else c(h, "dim")
    return f"{nm} {hc}" + c(f"h/{tests:<6}t {_ago(mtime):>7}", "dim")


def _ago(mtime: float) -> str:
    if not mtime:
        return "?"
    d = max(0, time.time() - mtime)
    if d < 90:
        return f"{int(d)}s ago"
    if d < 5400:
        return f"{int(d / 60)}m ago"
    if d < 172800:
        return f"{int(d / 3600)}h ago"
    return f"{int(d / 86400)}d ago"


def list_idle_results(active_names: set) -> list:
    """Result dirs in results/ that no live process is writing.

    Returns [(name, hits, tests, mtime), ...] sorted newest-first. Hits come
    from window-hits.txt (cheap line count); tests from window-results.json
    length. Helper/scratch dirs (leading underscore) are skipped.
    """
    base = ROOT / "results"
    rows = []
    if not base.is_dir():
        return rows
    for d in sorted(base.iterdir()):
        if (not d.is_dir() or d.is_symlink() or d.name.startswith("_")
                or d.name in active_names):
            continue
        # flat (<mode>/) and per-kind testrun (<mode>/<kind>/) layouts both.
        res_files = (list(d.glob("window-results.json"))
                     + list(d.glob("*/window-results.json"))
                     + list(d.glob("*/*/window-results.json")))
        if not res_files:
            continue
        hits = tests = 0
        mtime = 0.0
        for rf in res_files:
            try:
                mtime = max(mtime, rf.stat().st_mtime)
            except OSError:
                pass
            tests += json_len(rf)
        for hf in (list(d.glob("window-hits.txt"))
                   + list(d.glob("*/window-hits.txt"))
                   + list(d.glob("*/*/window-hits.txt"))):
            try:
                hits += sum(1 for ln in hf.read_text().splitlines() if ln.strip())
            except OSError:
                pass
        rows.append((d.name, hits, tests, mtime))
    rows.sort(key=lambda r: r[3], reverse=True)
    return rows


def _safe_cfg(cfgpath: str) -> dict:
    try:
        return load_jsonc(resolve(cfgpath))
    except Exception:
        return {"paths": {}}


# ── freshness / hung detection ───────────────────────────────────────────────
# Per-section monotonic progress signal + the wall-clock time it last advanced.
# Persists across refreshes within the monitor process. A section is HUNG if it
# has work to do but its signal hasn't moved for >= stale_secs.
_PROG: dict = {}


def freshness(key, value: int, has_work: bool, stale_secs: int):
    """Return (state, idle_secs). state ∈ {new, cooking, waiting, hung}."""
    now = time.time()
    rec = _PROG.get(key)
    if rec is None:
        _PROG[key] = [value, now]
        return ("new", 0.0)
    last_val, last_ts = rec
    if value != last_val:
        rec[0], rec[1] = value, now
        return ("cooking", 0.0)
    if not has_work:
        rec[1] = now              # nothing to do → reset the clock, no alarm
        return ("waiting", 0.0)
    idle = now - last_ts
    return ("hung", idle) if idle >= stale_secs else ("cooking", idle)


def _emit_section(out: list, color: str, title: str, body: list,
                  state: str, idle: float, alerts: list) -> None:
    """Append a section; wrap it in a big red box if state == 'hung'."""
    if state == "hung":
        mins = int(idle / 60)
        banner = f" 🚨 HUNG — no new results in {mins}m — CHECK THIS 🚨 "
        rule = "━" * 64
        out.append(c("┏" + rule, "red", "bold"))
        out.append(c(banner, "bold", "bgred"))
        out.append(c("┃ ", "red", "bold") + c(title.lstrip("▌ "), "bold", "red"))
        for ln in body:
            out.append(c("┃ ", "red", "bold") + ln)
        out.append(c("┗" + rule, "red", "bold"))
        alerts.append(f"{title.split('→')[0].strip().lstrip('▌ ')} "
                      f"— frozen {mins}m")
        return
    chip = {"new":     c("● starting", "dim"),
            "cooking": c("● cooking", "grn", "bold"),
            "waiting": c("◌ waiting (no input ready)", "yel"),
            }.get(state, "")
    out.append("")
    out.append(c(title, "bold", color) + "   " + chip)
    out.extend(body)


def _scan_hits(results_name: str, base: Path, modes: list, hits_now: dict,
               prev_hits: dict) -> list:
    """Update per-kind hit counts and return [(mode, kind, count, gained), ...].
    Display-only: 'gained' just colors moved counts; the actual bell/banner is
    driven by the known-vs-new triage (see triage_line)."""
    kh = scan_kind_hits(base, modes)
    rows = []
    for (mode, kind), n in sorted(
            kh.items(),
            key=lambda kv: (modes.index(kv[0][0]) if kv[0][0] in modes else 0,
                            KIND_ORDER.get(kv[0][1], 9))):
        key = (results_name, mode, kind)
        hits_now[key] = n
        prev = prev_hits.get(key)
        gained = prev is not None and n > prev
        rows.append((mode, kind, n, gained))
    return rows


def _hits_line(rows: list) -> str:
    """One-line hit breakdown for a section: per-mode, split by transmitter kind
    when the layout partitions (ld / br_x / other_x)."""
    total = sum(n for _, _, n, _ in rows)
    by_mode: dict = {}
    for mode, kind, n, gained in rows:
        by_mode.setdefault(mode, []).append((kind, n, gained))

    def _seg(text: str, n: int, gained: bool) -> str:
        return (c(text, "red", "bold") if gained
                else c(text, "grn") if n else c(text, "dim"))

    parts = []
    for mode, items in by_mode.items():
        if len(items) == 1 and items[0][0] is None:        # no kind partition
            kind, n, gained = items[0]
            lbl = "" if mode is None else f"{mode}: "
            parts.append(_seg(f"{lbl}{n}", n, gained))
        else:
            kbits = [_seg(f"{kind}:{n}", n, gained)
                     for kind, n, gained in items]
            mtot = sum(n for _, n, _ in items)
            head = (c(f"{mode} ", "bold") if mode else "") + \
                c(f"{mtot}", "bold" if mtot else "dim")
            parts.append(f"{head}[" + " ".join(kbits) + "]")
    head = c("hits", "bold", "grn" if total else "dim")
    return f"{head}  {c(str(total), 'bold')}   " + "   ".join(parts)


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", type=int, default=60,
                    help="refresh seconds (default 60)")
    ap.add_argument("--once", action="store_true", help="draw once and exit")
    ap.add_argument("--no-bell", action="store_true", help="silence the bell")
    ap.add_argument("--stale-mins", type=float, default=10.0,
                    help="flag a running sweep as HUNG after this many minutes "
                         "with no new results (default 10)")
    a = ap.parse_args()

    stale_secs = int(a.stale_mins * 60)
    prev_hits: dict = {}
    try:
        while True:
            screen, hits_now, alerts = render(prev_hits, stale_secs)
            sys.stdout.write("\033[2J\033[H")  # clear + home
            sys.stdout.write(screen + "\n")
            if alerts and not a.no_bell:
                sys.stdout.write(BELL)
            sys.stdout.flush()
            prev_hits = hits_now
            if a.once:
                break
            time.sleep(a.interval)
    except KeyboardInterrupt:
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
