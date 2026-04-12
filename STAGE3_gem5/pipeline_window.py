#!/usr/bin/env python3
"""
pipeline_window.py  –  checks whether the xmit instruction issues inside
the speculative window defined by:

    last_committed.retire < xmit.issue < first_noncommitted.retire

If first_noncommitted is squashed (retire==0), the upper bound is infinity
(xmit just needs to issue after last_committed retired).

Usage:
    python3 pipeline_window.py <input_dir> [--jobs N] [--out results.json]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

GEM5_DIR  = Path("/work/gem5-recon")
GEM5_BIN  = GEM5_DIR / "build/X86/gem5.opt"
SE_CONFIG = GEM5_DIR / "configs/example/se.py"

GEM5_CPU      = "X86O3CPU"
GEM5_SCHEME   = 2  # default; overridden by --scheme arg
GEM5_DBG_FLAG = "O3PipeView"

_scheme = GEM5_SCHEME  # active scheme, set from CLI in main()
GEM5_DBG_FILE = "pipeview.txt"


def _entry_asm(func_name):
    return textwrap.dedent(f"""\
        .global _start
        .section .text
        _start:
            call "{func_name}"
            mov $60, %rax
            xor %rdi, %rdi
            syscall
    """)


def build_binary(s_path, workdir):
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


def _func_base_addr(binary, func_name):
    try:
        out = subprocess.check_output(["objdump", "-d", str(binary)],
                                      text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None
    m = re.search(r'^([0-9a-f]+) <' + re.escape(func_name) + r'>:',
                  out, re.MULTILINE)
    return int(m.group(1), 16) if m else None


def resolve_pc(binary, func_name, ann_entry):
    offset = ann_entry.get("x86_offset")
    if offset is None:
        return None
    base = _func_base_addr(binary, func_name)
    return (base + offset) if base is not None else None


def run_gem5(binary, workdir):
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


def _parse_pipeview(trace_path):
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
                    yield cur
                    cur = None


def _best_record(recs):
    """Pick the record with the highest stage reached."""
    ORDER = ["fetch","decode","rename","dispatch","issue","complete","retire"]
    def score(r):
        for s in reversed(ORDER):
            if r[s] > 0:
                return ORDER.index(s)
        return -1
    return max(recs, key=score) if recs else None


def check_window(trace_path, xmit_pc, lc_pc, fnc_pc):
    """
    Check: lc_retire < xmit.issue < fnc_retire
    If fnc_retire == 0 (squashed), upper bound is infinity.
    """
    by_pc = defaultdict(list)
    for r in _parse_pipeview(trace_path):
        by_pc[r["pc"]].append(r)

    xmit_rec = _best_record(by_pc.get(xmit_pc, []))
    lc_rec   = _best_record(by_pc.get(lc_pc,   [])) if lc_pc  else None
    fnc_rec  = _best_record(by_pc.get(fnc_pc,  [])) if fnc_pc else None

    xmit_issue    = xmit_rec["issue"]   if xmit_rec else 0
    xmit_complete = xmit_rec["complete"] if xmit_rec else 0
    lc_retire     = lc_rec["retire"]    if lc_rec   else 0
    fnc_retire    = fnc_rec["retire"]   if fnc_rec  else 0

    # window: lc_retire < xmit.issue < fnc_retire
    # if lc not found, skip the lower bound check
    # if fnc_retire == 0 (squashed), skip the upper bound check
    # after_lc       = (lc_retire == 0) or (xmit_issue > lc_retire)
    # before_fnc     = (fnc_retire == 0) or (xmit_issue < fnc_retire)
    after_lc       = (lc_retire == 0) or (xmit_complete > lc_retire)
    before_fnc     = (fnc_retire == 0) or (xmit_complete < fnc_retire)
    issued_in_window = (xmit_complete > 0) and after_lc and before_fnc

    return dict(
        issued_in_window=issued_in_window,
        xmit_issue=xmit_issue,
        xmit_complete=xmit_complete,
        lc_retire=lc_retire,
        fnc_retire=fnc_retire,
    )


def process_one(s_path, ann_path, keep_tmp):
    name    = s_path.stem
    workdir = Path(tempfile.mkdtemp(prefix=f"gem5win_{name}_"))
    result  = dict(name=name, status="ok",
                   xmit_pc=None, last_committed_pc=None, first_noncommitted_pc=None,
                   xmit_kind=None, issued_in_window=None,
                   xmit_issue=None, xmit_complete=None,
                   lc_retire=None, fnc_retire=None, error=None)
    try:
        ann  = json.loads(ann_path.read_text())
        xmit = ann.get("xmit", {})
        cb   = ann.get("commit_boundary", {})
        lc   = cb.get("last_committed", {})
        fnc  = cb.get("first_noncommitted", {})

        result["xmit_kind"] = xmit.get("kind", "")

        binary  = build_binary(s_path, workdir)
        xmit_pc = resolve_pc(binary, name, xmit)
        lc_pc   = resolve_pc(binary, name, lc)
        fnc_pc  = resolve_pc(binary, name, fnc)

        result["xmit_pc"]               = hex(xmit_pc)  if xmit_pc  else None
        result["last_committed_pc"]     = hex(lc_pc)    if lc_pc    else None
        result["first_noncommitted_pc"] = hex(fnc_pc)   if fnc_pc   else None

        if xmit_pc is None:
            result["status"] = "warn"
            result["error"]  = "no xmit x86 PC"
        else:
            trace = run_gem5(binary, workdir)
            result.update(check_window(trace, xmit_pc, lc_pc, fnc_pc))

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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input_dir", type=Path)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--keep-tmp", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--scheme", type=int, default=GEM5_SCHEME,
                    help=f"gem5 --scheme value (default: {GEM5_SCHEME})")
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
        else:
            print(f"[warn] no annotation for {s_path.name}, skipping")

    if not pairs:
        sys.exit("error: no .s / .ann.json pairs found")

    print(f"Found {len(pairs)} test(s) in {input_dir}")
    print(f"gem5 scheme={_scheme}  jobs={args.jobs}\n")

    results = []

    def _tag(v):
        return {True: "YES", False: "NO ", None: "???"}[v]

    def run(pair):
        s, a = pair
        r = process_one(s, a, args.keep_tmp)
        tag  = _tag(r["issued_in_window"])
        xpc  = r["xmit_pc"] or "n/a"
        kind = r["xmit_kind"] or "?"
        lc_t = r["lc_retire"]   or 0
        xi_t = r["xmit_issue"]  or 0
        fn_t = r["fnc_retire"]  or 0
        print(f"  [{tag}] {r['name']:20s}  xmit={xpc}({kind})"
              f"  lc_ret={lc_t}  xmit_iss={xi_t}  fnc_ret={fn_t}  [{r['status'].upper()}]"
              + (f"  {r['error'][:60]}" if r["error"] else ""))
        return r

    if args.jobs == 1:
        for pair in pairs:
            results.append(run(pair))
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(process_one, s, a, args.keep_tmp): (s, a)
                    for s, a in pairs}
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                tag  = _tag(r["issued_in_window"])
                xpc  = r["xmit_pc"] or "n/a"
                kind = r["xmit_kind"] or "?"
                lc_t = r["lc_retire"]  or 0
                xi_t = r["xmit_issue"] or 0
                fn_t = r["fnc_retire"] or 0
                print(f"  [{tag}] {r['name']:20s}  xmit={xpc}({kind})"
                      f"  lc_ret={lc_t}  xmit_iss={xi_t}  fnc_ret={fn_t}"
                      + (f"  ERROR: {r['error'][:60]}" if r["error"] else ""))

    yes = sum(1 for r in results if r["issued_in_window"] is True)
    no  = sum(1 for r in results if r["issued_in_window"] is False)
    err = sum(1 for r in results if r["status"] != "ok")
    print(f"\nResults: {yes} issued in window  |  {no} did not  |  {err} error(s)  (total {len(results)})")

    if args.out:
        args.out.write_text(json.dumps(results, indent=2))
        print(f"Full results written to {args.out}")


if __name__ == "__main__":
    main()
