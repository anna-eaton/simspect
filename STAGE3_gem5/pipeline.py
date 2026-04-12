#!/usr/bin/env python3
"""
pipeline.py  –  batch gem5 runner + xmit-completion checker

For every <name>.s / <name>.ann.json pair in INPUT_DIR:
  1. Build a static ELF  (entry stub + assembled .s)
  2. Run gem5  (X86O3CPU, --caches, --scheme=2, O3PipeView debug trace)
  3. Parse the pipeview trace and report whether the xmit instruction
     ever completed (issue > 0 AND complete > 0), even if later squashed.

Usage:
    python3 pipeline.py <input_dir> [--jobs N] [--keep-tmp] [--out results.json]
"""

import argparse
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

# ── fixed paths ──────────────────────────────────────────────────────────────
GEM5_DIR  = Path("/work/gem5-recon")
GEM5_BIN  = GEM5_DIR / "build/X86/gem5.opt"
SE_CONFIG = GEM5_DIR / "configs/example/se.py"

# gem5 run parameters (mirrors run-inst-000003.json)
GEM5_CPU      = "X86O3CPU"
GEM5_SCHEME   = 2  # default; overridden by --scheme arg
GEM5_DBG_FLAG = "O3PipeView"

_scheme = GEM5_SCHEME
GEM5_DBG_FILE = "pipeview.txt"


# ── helpers: build ────────────────────────────────────────────────────────────

def _entry_asm(func_name: str) -> str:
    """Return assembly source for a _start stub that calls func_name then exits."""
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
    """
    Assemble s_path + a _start entry stub into a static ELF.
    Returns the path to the produced binary.
    Raises subprocess.CalledProcessError on failure.
    """
    func_name = s_path.stem          # e.g. "inst-000001"
    binary    = workdir / func_name

    # ── patch the .s: remove .addrsig (unsupported by binutils GAS) ──
    patched_s = workdir / (func_name + "_patched.s")
    text = s_path.read_text()
    text = re.sub(r'^\s*\.addrsig\s*$', '', text, flags=re.MULTILINE)
    patched_s.write_text(text)

    # ── write entry stub ──
    entry_s = workdir / "_entry.s"
    entry_s.write_text(_entry_asm(func_name))

    # ── assemble both ──
    func_o  = workdir / "func.o"
    entry_o = workdir / "entry.o"
    subprocess.run(["as", "-o", str(func_o),  str(patched_s)], check=True,
                   capture_output=True)
    subprocess.run(["as", "-o", str(entry_o), str(entry_s)],   check=True,
                   capture_output=True)

    # ── link (static) ──
    subprocess.run(["ld", "-static", "-o", str(binary),
                    str(entry_o), str(func_o)],
                   check=True, capture_output=True)

    return binary


# ── helpers: find xmit x86 PC ────────────────────────────────────────────────

def _func_base_addr(binary: Path, func_name: str):
    """Return the load address of func_name's first byte, or None."""
    try:
        out = subprocess.check_output(["objdump", "-d", str(binary)],
                                      text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None
    m = re.search(r'^([0-9a-f]+) <' + re.escape(func_name) + r'>:',
                  out, re.MULTILINE)
    return int(m.group(1), 16) if m else None


def find_xmit_x86_pc(binary: Path, func_name: str, xmit: dict):
    """
    Use xmit['x86_offset'] + function base address to get the actual x86 PC.
    Returns None if offset is missing or function not found.
    """
    offset = xmit.get("x86_offset")
    if offset is None:
        return None
    base = _func_base_addr(binary, func_name)
    if base is None:
        return None
    return base + offset


# ── helpers: run gem5 ─────────────────────────────────────────────────────────

def run_gem5(binary: Path, workdir: Path) -> Path:
    """
    Run gem5 in SE mode on binary; return path to the pipeview trace file.
    Raises subprocess.CalledProcessError on failure.
    """
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
    subprocess.run(cmd, check=True, capture_output=True, cwd=str(GEM5_DIR))
    return outdir / GEM5_DBG_FILE


# ── helpers: parse pipeview ───────────────────────────────────────────────────

def _parse_pipeview(trace_path: Path):
    """
    Yield dicts per instruction record:
      {pc, upc, seq, fetch, decode, rename, dispatch, issue, complete, retire}
    """
    cur = None
    with open(trace_path) as f:
        for line in f:
            if not line.startswith("O3PipeView:"):
                continue
            parts = line.rstrip().split(":")
            stage = parts[1]
            if stage == "fetch":
                cur = dict(
                    pc       = int(parts[3], 16),
                    upc      = int(parts[4]),
                    seq      = int(parts[5]),
                    disasm   = parts[6].strip() if len(parts) > 6 else "",
                    fetch    = int(parts[2]),
                    decode=0, rename=0, dispatch=0,
                    issue=0, complete=0, retire=0,
                )
            elif stage in ("decode","rename","dispatch","issue","complete"):
                if cur:
                    cur[stage] = int(parts[2])
            elif stage == "retire":
                if cur:
                    cur["retire"] = int(parts[2])
                    yield cur
                    cur = None


def xmit_completed(trace_path: Path, xmit_pc: int) -> bool:
    """
    Return True if any record at xmit_pc has complete > 0
    (the instruction actually executed in the pipeline).
    """
    for r in _parse_pipeview(trace_path):
        if r["pc"] == xmit_pc and r["complete"] > 0:
            return True
    return False


# ── per-test worker ───────────────────────────────────────────────────────────

def process_one(s_path: Path, ann_path: Path, keep_tmp: bool,
                traces_dir: Path = None) -> dict:
    """
    Full pipeline for one test.  Returns a result dict.
    """
    name     = s_path.stem
    workdir  = Path(tempfile.mkdtemp(prefix=f"gem5pipe_{name}_"))
    result   = dict(name=name, status="ok", completed=None,
                    xmit_pc_x86=None, xmit_kind=None, error=None)
    try:
        # ── load annotation ──
        ann  = json.loads(ann_path.read_text())
        xmit = ann.get("xmit", {})
        kind = xmit.get("kind", "")

        result["xmit_kind"] = kind

        # ── build ──
        binary = build_binary(s_path, workdir)

        # ── find xmit x86 PC ──
        xmit_pc = find_xmit_x86_pc(binary, name, xmit)
        result["xmit_pc_x86"] = hex(xmit_pc) if xmit_pc is not None else None

        # ── run gem5 ──
        trace = run_gem5(binary, workdir)

        # ── save trace if requested ──
        if traces_dir is not None:
            shutil.copy(trace, traces_dir / f"{name}.pipeview.txt")

        # ── check completion ──
        if xmit_pc is not None:
            result["completed"] = xmit_completed(trace, xmit_pc)
        else:
            result["status"] = "warn"
            result["error"]  = "could not identify xmit x86 PC"

    except subprocess.CalledProcessError as e:
        result["status"] = "error"
        result["error"]  = (e.stderr or b"").decode(errors="replace")[-400:]
    except Exception as e:
        result["status"] = "error"
        result["error"]  = str(e)
    finally:
        if not keep_tmp:
            shutil.rmtree(workdir, ignore_errors=True)
        else:
            result["workdir"] = str(workdir)

    return result


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir", type=Path,
                    help="directory containing .s and .ann.json files")
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel workers (default: 1)")
    ap.add_argument("--keep-tmp", action="store_true",
                    help="do not delete per-test temp directories")
    ap.add_argument("--out", type=Path, default=None,
                    help="write JSON results to this file")
    ap.add_argument("--save-traces", type=Path, default=None,
                    help="directory to copy each pipeview.txt into (created if needed)")
    ap.add_argument("--scheme", type=int, default=GEM5_SCHEME,
                    help=f"gem5 --scheme value (default: {GEM5_SCHEME})")
    args = ap.parse_args()

    global _scheme
    _scheme = args.scheme

    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        sys.exit(f"error: {input_dir} is not a directory")

    # ── collect pairs ──
    pairs = []
    for s_path in sorted(input_dir.glob("*.s")):
        ann_path = s_path.with_suffix(".ann.json")
        if ann_path.exists():
            pairs.append((s_path, ann_path))
        else:
            print(f"[warn] no annotation for {s_path.name}, skipping")

    if not pairs:
        sys.exit("error: no .s / .ann.json pairs found")

    traces_dir = args.save_traces
    if traces_dir is not None:
        traces_dir.mkdir(parents=True, exist_ok=True)
        print(f"Traces will be saved to: {traces_dir}")

    print(f"Found {len(pairs)} test(s) in {input_dir}")
    print(f"gem5 scheme={_scheme}  jobs={args.jobs}\n")

    results = []

    def run(pair):
        s, a = pair
        r = process_one(s, a, args.keep_tmp, traces_dir)
        tag = {True: "YES", False: "NO ", None: "???"}[r["completed"]]
        status = r["status"].upper()
        xpc    = r["xmit_pc_x86"] or "n/a"
        kind   = r["xmit_kind"]   or "?"
        print(f"  [{tag}] {r['name']:20s}  xmit={xpc} ({kind:8s})  [{status}]"
              + (f"  {r['error'][:60]}" if r["error"] else ""))
        return r

    if args.jobs == 1:
        for pair in pairs:
            results.append(run(pair))
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(process_one, s, a, args.keep_tmp, traces_dir): (s, a)
                    for s, a in pairs}
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                tag = {True: "YES", False: "NO ", None: "???"}[r["completed"]]
                xpc  = r["xmit_pc_x86"] or "n/a"
                kind = r["xmit_kind"]   or "?"
                print(f"  [{tag}] {r['name']:20s}  xmit={xpc} ({kind:8s})"
                      + (f"  ERROR: {r['error'][:60]}" if r["error"] else ""))

    # ── summary ──
    yes   = sum(1 for r in results if r["completed"] is True)
    no    = sum(1 for r in results if r["completed"] is False)
    err   = sum(1 for r in results if r["status"] != "ok")
    print(f"\nResults: {yes} completed  |  {no} did not  |  {err} error(s)"
          f"  (total {len(results)})")

    if args.out:
        args.out.write_text(json.dumps(results, indent=2))
        print(f"Full results written to {args.out}")


if __name__ == "__main__":
    main()
