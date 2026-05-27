#!/usr/bin/env python3
"""
gem5_common.py — shared infrastructure for per-transmitter gem5 checker scripts.

Provides:
  - build_binary()   — assemble + link a litmus test into a static x86-64 ELF
  - run_gem5()       — invoke gem5 with O3PipeView tracing
  - parse_pipeview() — parse O3PipeView trace into per-instruction records
  - best_record()    — pick the record with the highest pipeline stage reached
  - resolve_pc()     — annotation x86_offset → absolute PC via objdump
  - load_annotation()— load .ann.json and extract xmit / commit-boundary entries
  - run_batch()      — batch runner: pairs up .s + .ann.json, dispatches to a
                        check function, writes results JSON
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


def sample_keep(stem: str, fraction: float) -> bool:
    """Deterministic stem-hash filter for sub-sampling a testset.

    Returns True if `stem` should be kept. The 8-hex-digit md5 prefix gives a
    stable mapping across Python versions / machines, so the recon, sttbuild
    and amulet tracks all pick the same subset of a shared testset.
    """
    if fraction >= 1.0:
        return True
    if fraction <= 0.0:
        return False
    h = int(hashlib.md5(stem.encode()).hexdigest()[:8], 16)
    return (h / 0xFFFFFFFF) < fraction

# ── Defaults (overridden at runtime by run_batch / CLI / env) ────────────────
#
# The SIMSPECT_GEM5_* environment variables let pipeline.py point the checkers
# at an alternate gem5 build (e.g. /work/gem5-recon-modded) without editing
# source. run_config.jsonc's "gem5.binary" / "gem5.config_script" fields are
# plumbed through as these env vars.

GEM5_DIR  = Path(os.environ.get("SIMSPECT_GEM5_DIR",  "/work/gem5-recon"))
GEM5_BIN  = Path(os.environ.get("SIMSPECT_GEM5_BIN",  str(GEM5_DIR / "build/X86/gem5.opt")))
SE_CONFIG = Path(os.environ.get("SIMSPECT_SE_CONFIG", str(GEM5_DIR / "configs/example/se.py")))
GEM5_CPU  = os.environ.get("SIMSPECT_GEM5_CPU",  "X86O3CPU")
GEM5_DBG_FLAG = os.environ.get("SIMSPECT_GEM5_DBG_FLAG", "O3PipeView")
GEM5_DBG_FILE = os.environ.get("SIMSPECT_GEM5_DBG_FILE", "pipeview.txt")

# When truthy, run_gem5() injects --branch-ann-file=<test>.ann.json plus an
# auto-resolved --branch-ann-base. Requires a gem5 build that supports those
# options (i.e. /work/gem5-recon-modded).
BRANCH_ANN_ENABLE = os.environ.get("SIMSPECT_BRANCH_ANN_ENABLE", "").lower() in (
    "1", "true", "yes", "on")

ALLOW_LEAKED = os.environ.get("SIMSPECT_ALLOW_LEAKED", "").lower() in (
    "1", "true", "yes", "on")

FNC_COMMIT_STALL_CYCLES: int = int(os.environ.get("SIMSPECT_FNC_COMMIT_STALL_CYCLES", "0"))

_scheme: int = 2   # mutable; set by run_batch() from CLI


# ── Build helpers ────────────────────────────────────────────────────────────

def _entry_asm(func_name: str) -> str:
    return textwrap.dedent(f"""\
        .global _start
        .section .text
        _start:
            call "{func_name}"
            mov $60, %rax
            xor %rdi, %rdi
            syscall
    """)


def build_binary(s_path: Path, workdir: Path) -> Path:
    func_name = s_path.stem
    binary    = workdir / func_name
    patched_s = workdir / (func_name + "_patched.s")
    text = s_path.read_text()
    text = re.sub(r'^\s*\.addrsig\s*$', '', text, flags=re.MULTILINE)
    patched_s.write_text(text)
    entry_s = workdir / "_entry.s"
    entry_s.write_text(_entry_asm(func_name))
    func_o  = workdir / "func.o"
    entry_o = workdir / "entry.o"
    subprocess.run(["as", "-o", str(func_o),  str(patched_s)], check=True, capture_output=True)
    subprocess.run(["as", "-o", str(entry_o), str(entry_s)],   check=True, capture_output=True)
    subprocess.run(["ld", "-static", "-o", str(binary), str(entry_o), str(func_o)],
                   check=True, capture_output=True)
    return binary


# ── PC resolution ────────────────────────────────────────────────────────────

def _func_base_addr(binary: Path, func_name: str) -> Optional[int]:
    try:
        out = subprocess.check_output(["objdump", "-d", str(binary)],
                                      text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None
    m = re.search(r'^([0-9a-f]+) <' + re.escape(func_name) + r'>:',
                  out, re.MULTILINE)
    return int(m.group(1), 16) if m else None


def resolve_pc(binary: Path, func_name: str, ann_entry: dict) -> Optional[int]:
    offset = ann_entry.get("x86_offset")
    if offset is None:
        return None
    base = _func_base_addr(binary, func_name)
    return (base + offset) if base is not None else None


# ── gem5 simulation ──────────────────────────────────────────────────────────

def run_gem5(binary: Path, workdir: Path,
             ann_path: Optional[Path] = None,
             fnc_pc: Optional[int] = None) -> Path:
    outdir = workdir / "m5out"
    outdir.mkdir(exist_ok=True)
    cmd = [
        str(GEM5_BIN),
        f"--outdir={outdir}",
        f"--debug-flags={GEM5_DBG_FLAG}",
        f"--debug-file={GEM5_DBG_FILE}",
        str(SE_CONFIG),
        f"--cmd={binary}",
        f"--cpu-type={GEM5_CPU}",
        "--caches",
        f"--scheme={_scheme}",
    ]

    if BRANCH_ANN_ENABLE and ann_path is not None and ann_path.exists():
        base = _func_base_addr(binary, binary.stem)
        cmd.append(f"--branch-ann-file={ann_path}")
        if base is not None:
            cmd.append(f"--branch-ann-base={hex(base)}")

    if ALLOW_LEAKED:
        cmd.append("--allow_leaked")

    if fnc_pc is not None and FNC_COMMIT_STALL_CYCLES > 0:
        cmd.append(f"--fnc-commit-stall-pc={hex(fnc_pc)}")
        cmd.append(f"--fnc-commit-stall-cycles={FNC_COMMIT_STALL_CYCLES}")

    subprocess.run(cmd, check=True, capture_output=True, cwd=str(GEM5_DIR))
    return outdir / GEM5_DBG_FILE


# ── Pipeview parsing ────────────────────────────────────────────────────────

def parse_pipeview(trace_path: Path) -> Dict[int, List[dict]]:
    """Parse O3PipeView trace → dict mapping PC → list of pipeline records."""
    by_pc: Dict[int, List[dict]] = defaultdict(list)
    cur = None
    with open(trace_path) as f:
        for line in f:
            if not line.startswith("O3PipeView:"):
                continue
            parts = line.rstrip().split(":")
            stage = parts[1]
            if stage == "fetch":
                cur = dict(pc=int(parts[3], 16),
                           fetch=int(parts[2]), decode=0, rename=0, dispatch=0,
                           issue=0, complete=0, retire=0)
            elif stage in ("decode", "rename", "dispatch", "issue", "complete"):
                if cur:
                    cur[stage] = int(parts[2])
            elif stage == "retire":
                if cur:
                    cur["retire"] = int(parts[2])
                    by_pc[cur["pc"]].append(cur)
                    cur = None
    return dict(by_pc)


def best_record(recs: List[dict]) -> Optional[dict]:
    """Pick the record with the highest pipeline stage reached.

    For micro-coded x86 instructions (e.g. JNZ_I → 3 micro-ops at the same
    PC), multiple records share a PC. When several reach `retire`, prefer
    the one with the latest retire-tick — that's the micro-op that actually
    completes the macro-op (e.g. the `wrip` redirect of a jne, whose retire
    is delayed by the resolution-stall mechanism).
    """
    ORDER = ["fetch", "decode", "rename", "dispatch", "issue", "complete", "retire"]
    def score(r):
        for s in reversed(ORDER):
            if r[s] > 0:
                return (ORDER.index(s), r["retire"], r["complete"])
        return (-1, 0, 0)
    return max(recs, key=score) if recs else None


# ── Annotation loading ──────────────────────────────────────────────────────

def load_annotation(ann_path: Path) -> dict:
    """Load .ann.json and return structured dict with xmit / commit_boundary."""
    ann = json.loads(ann_path.read_text())
    return dict(
        xmit=ann.get("xmit", {}),
        lc=ann.get("commit_boundary", {}).get("last_committed", {}),
        fnc=ann.get("commit_boundary", {}).get("first_noncommitted", {}),
        annotations=ann.get("annotations", []),
    )


def parse_ticks_per_cycle(outdir: Path) -> int:
    """Read system.cpu_clk_domain.clock from m5out/config.json → ticks/cycle.

    Falls back to 500 (2 GHz @ 1 ps tick) if the field is absent.
    """
    cfg = json.loads((outdir / "config.json").read_text())
    try:
        clk = cfg["system"]["cpu_clk_domain"]["clock"]
        return int(clk[0]) if isinstance(clk, list) else int(clk)
    except (KeyError, TypeError):
        return 500


def collect_unresolved_branches(ann_full: dict, binary: Path,
                                func_name: str) -> List[dict]:
    """Return list of {pc, stall_cycles} for entries with resolve_stall_cycles > 0.

    PC is resolved via x86_branch_offset + func base (the jne PC, matching the
    same PC gem5 will hit in iew_impl.hh for the deferred-resolution hook).
    """
    base = _func_base_addr(binary, func_name)
    if base is None:
        return []
    out: List[dict] = []
    for e in ann_full.get("annotations", []):
        stall = int(e.get("resolve_stall_cycles", 0) or 0)
        if stall <= 0:
            continue
        bxo = e.get("x86_branch_offset")
        if bxo is None:
            continue
        out.append(dict(pc=base + int(bxo), stall_cycles=stall))
    return out


def check_branch_resolutions(by_pc: Dict[int, list],
                             xmit_complete: int,
                             unresolved: List[dict],
                             ticks_per_cycle: int) -> Tuple[bool, List[dict]]:
    """For each unresolved branch, prop_tick = complete + stall*ticks/cycle.

    Returns (all_unresolved_ok, per_branch_details).  A branch counts as
    "still unresolved at xmit_complete" if either:
      (a) it was never fetched / never completed (resolution never propagated)
      (b) xmit_complete < prop_tick
    The caller should already have excluded xmit_pc from `unresolved`.
    """
    details: List[dict] = []
    all_ok = True
    for u in unresolved:
        rec = best_record(by_pc.get(u["pc"], []))
        complete = rec.get("complete", 0) if rec else 0
        if complete == 0:
            details.append(dict(pc=hex(u["pc"]), stall=u["stall_cycles"],
                                complete=0, prop_tick=0, ok=True,
                                reason="not completed"))
            continue
        prop_tick = complete + u["stall_cycles"] * ticks_per_cycle
        ok = xmit_complete < prop_tick
        details.append(dict(pc=hex(u["pc"]), stall=u["stall_cycles"],
                            complete=complete, prop_tick=prop_tick, ok=ok))
        if not ok:
            all_ok = False
    return all_ok, details


# ── Generic process_one ─────────────────────────────────────────────────────

# Type alias for a check function:
#   check_fn(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved, ticks_per_cycle)
#     → dict with at least "issued_in_window"
CheckFn = Callable[[Dict[int, list], Optional[int], Optional[int], Optional[int],
                    List[dict], int], dict]


def process_one(s_path: Path, ann_path: Path, check_fn: CheckFn,
                keep_tmp: bool = False) -> dict:
    name    = s_path.stem
    workdir = Path(tempfile.mkdtemp(prefix=f"gem5_{name}_"))
    result  = dict(name=name, status="ok",
                   xmit_pc=None, last_committed_pc=None, first_noncommitted_pc=None,
                   xmit_kind=None, issued_in_window=None,
                   xmit_issue=None, xmit_complete=None,
                   lc_retire=None, fnc_retire=None, fnc_complete=None,
                   error=None)
    try:
        parts   = load_annotation(ann_path)
        xmit    = parts["xmit"]
        lc      = parts["lc"]
        fnc     = parts["fnc"]

        result["xmit_kind"] = xmit.get("kind", "")

        binary  = build_binary(s_path, workdir)
        xmit_pc = resolve_pc(binary, name, xmit)
        lc_pc   = resolve_pc(binary, name, lc)
        fnc_pc  = resolve_pc(binary, name, fnc)

        result["xmit_pc"]               = hex(xmit_pc) if xmit_pc else None
        result["last_committed_pc"]     = hex(lc_pc)   if lc_pc   else None
        result["first_noncommitted_pc"] = hex(fnc_pc)  if fnc_pc  else None

        if xmit_pc is None:
            result["status"] = "warn"
            result["error"]  = "no xmit x86 PC"
        else:
            trace = run_gem5(binary, workdir, ann_path=ann_path, fnc_pc=fnc_pc)
            by_pc = parse_pipeview(trace)
            ticks_per_cycle = parse_ticks_per_cycle(workdir / "m5out")
            unresolved = collect_unresolved_branches(
                dict(annotations=parts["annotations"]), binary, name)
            # The xmit PC, if itself an annotated unresolved branch, is the
            # event we're conditioning on — exclude it from the bound check.
            unresolved = [u for u in unresolved if u["pc"] != xmit_pc]
            check_result = check_fn(by_pc, xmit_pc, lc_pc, fnc_pc,
                                    unresolved, ticks_per_cycle)
            result.update(check_result)

    except subprocess.CalledProcessError as e:
        result["status"] = "error"
        stderr = (e.stderr or b"").decode(errors="replace")
        # gem5 aborts dump a libc/python backtrace whose tail is useless; the
        # actual cause is the "panic:"/"fatal:" line near the top. Surface it.
        cause = next((ln.strip() for ln in stderr.splitlines()
                      if ln.startswith(("panic:", "fatal:"))), None)
        result["error"] = (cause + " | " if cause else "") + stderr[-400:]
    except Exception as e:
        result["status"] = "error"
        result["error"]  = str(e)
    finally:
        if not keep_tmp:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            result["workdir"] = str(workdir)

    return result


# ── Batch runner ─────────────────────────────────────────────────────────────

def _tag(v):
    return {True: "YES", False: "NO ", None: "???"}[v]


def run_batch(check_fn: CheckFn, description: str = "window check") -> None:
    """
    CLI entry-point for a checker script.  Parses standard args, pairs up
    .s + .ann.json files, runs process_one with the given check_fn, and
    writes results JSON.
    """
    ap = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("--jobs",     type=int, default=1)
    ap.add_argument("--keep-tmp", action="store_true")
    ap.add_argument("--out",      type=Path, default=None)
    ap.add_argument("--scheme",   type=int, default=2,
                    help="gem5 --scheme value (default: 2)")
    ap.add_argument("--limit",    type=int, default=None,
                    help="Only process the first N tests")
    args = ap.parse_args()

    global _scheme
    _scheme = args.scheme

    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        sys.exit(f"error: {input_dir} is not a directory")

    pairs = []
    for s_path in sorted(input_dir.glob("*.s")):
        ann_path = s_path.with_suffix(".ann.json")
        if ann_path.exists():
            pairs.append((s_path, ann_path))

    if not pairs:
        sys.exit("error: no .s / .ann.json pairs found")

    if args.limit:
        pairs = pairs[:args.limit]

    print(f"Found {len(pairs)} test(s) in {input_dir}")
    print(f"gem5 scheme={_scheme}  jobs={args.jobs}  check={description}\n")

    results: List[dict] = []

    def _run(pair: Tuple[Path, Path]) -> dict:
        s, a = pair
        r = process_one(s, a, check_fn, args.keep_tmp)
        tag  = _tag(r["issued_in_window"])
        xpc  = r["xmit_pc"] or "n/a"
        kind = r["xmit_kind"] or "?"
        lc_t = r.get("lc_retire", 0)    or 0
        xc_t = r.get("xmit_complete", 0) or 0
        fn_t = r.get("fnc_retire", 0)   or 0
        print(f"  [{tag}] {r['name']:20s}  xmit={xpc}({kind})"
              f"  lc_ret={lc_t}  xmit_cmp={xc_t}  fnc_ret={fn_t}  [{r['status'].upper()}]"
              + (f"  {r['error'][:60]}" if r.get("error") else ""))
        return r

    if args.jobs == 1:
        for pair in pairs:
            results.append(_run(pair))
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(process_one, s, a, check_fn, args.keep_tmp): (s, a)
                    for s, a in pairs}
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                tag  = _tag(r["issued_in_window"])
                xpc  = r["xmit_pc"] or "n/a"
                kind = r["xmit_kind"] or "?"
                lc_t = r.get("lc_retire", 0)    or 0
                xc_t = r.get("xmit_complete", 0) or 0
                fn_t = r.get("fnc_retire", 0)   or 0
                print(f"  [{tag}] {r['name']:20s}  xmit={xpc}({kind})"
                      f"  lc_ret={lc_t}  xmit_cmp={xc_t}  fnc_ret={fn_t}"
                      + (f"  ERROR: {r['error'][:60]}" if r.get("error") else ""))

    yes = sum(1 for r in results if r["issued_in_window"] is True)
    no  = sum(1 for r in results if r["issued_in_window"] is False)
    err = sum(1 for r in results if r["status"] != "ok")
    print(f"\nResults: {yes} in window  |  {no} not in window  |  {err} error(s)  (total {len(results)})")

    if args.out:
        args.out.write_text(json.dumps(results, indent=2))
        print(f"Full results written to {args.out}")
