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
import ctypes
import json
import os
import re
import shutil
import signal
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
GEM5_DBG_FLAG = os.environ.get("SIMSPECT_GEM5_DBG_FLAG", "O3PipeView,LSQUnit")
GEM5_DBG_FILE = os.environ.get("SIMSPECT_GEM5_DBG_FILE", "pipeview.txt")

# When truthy, run_gem5() injects --branch-ann-file=<test>.ann.json plus an
# auto-resolved --branch-ann-base. Requires a gem5 build that supports those
# options (i.e. /work/gem5-recon-modded).
BRANCH_ANN_ENABLE = os.environ.get("SIMSPECT_BRANCH_ANN_ENABLE", "").lower() in (
    "1", "true", "yes", "on")

ALLOW_LEAKED = os.environ.get("SIMSPECT_ALLOW_LEAKED", "").lower() in (
    "1", "true", "yes", "on")

FNC_COMMIT_STALL_CYCLES: int = int(os.environ.get("SIMSPECT_FNC_COMMIT_STALL_CYCLES", "0"))

# Disk safety net: litmus runs finish in well under a second of wall time, so a
# run still alive after this many seconds is a runaway/livelock (e.g. the
# commitToIEWDelay>=5 livelock) whose unbounded O3PipeView trace will fill the
# disk — kill it. SIMSPECT_GEM5_MAX_TICK is belt-and-suspenders: a generous
# absolute-tick ceiling so gem5 self-exits cleanly long before a legit run
# would ever reach it (set so high it can only fire on a true runaway).
GEM5_TIMEOUT_S: int = int(os.environ.get("SIMSPECT_GEM5_TIMEOUT_S", "120"))
GEM5_MAX_TICK:  int = int(os.environ.get("SIMSPECT_GEM5_MAX_TICK", "100000000000"))

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
    # New schema: `addr` is the absolute PC, written by compile_annotate.py.
    addr = ann_entry.get("addr")
    if addr is not None:
        return int(addr)
    # Backward-compat: legacy ann.json files have function-relative `x86_offset`.
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
    # Always trace Commit too: check_br keys the branch-leak verdict on the
    # xmit's actual mispredict-squash broadcast tick (the observable redirect),
    # which a delay-based defense (STT implicit-channel) pushes out of the
    # window even though the branch resolves in-window. That tick is only in the
    # Commit debug log, not O3PipeView. Cheap for litmus-size traces.
    dbg_flags = (GEM5_DBG_FLAG if "Commit" in GEM5_DBG_FLAG.split(",")
                 else GEM5_DBG_FLAG + ",Commit")
    cmd = [
        str(GEM5_BIN),
        f"--outdir={outdir}",
        f"--debug-flags={dbg_flags}",
        f"--debug-file={GEM5_DBG_FILE}",
        str(SE_CONFIG),
        f"--cmd={binary}",
        f"--cpu-type={GEM5_CPU}",
        "--caches",
        f"--scheme={_scheme}",
    ]

    if GEM5_MAX_TICK > 0:
        cmd.append(f"--abs-max-tick={GEM5_MAX_TICK}")

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

    extra = os.environ.get("SIMSPECT_GEM5_EXTRA", "")
    if extra:
        cmd.extend(a for a in extra.split("\x1f") if a)

    _run_bounded(cmd)
    return outdir / GEM5_DBG_FILE


def _set_pdeathsig():
    """preexec (child side): SIGKILL this gem5 if the launching python dies.

    Without this, a killed sweep/session orphans gem5 to PID 1 where it keeps
    appending to its (often already-unlinked) pipeview.txt, pinning the disk at
    100% until manually killed. Linux-only; the platform here is Linux.
    """
    PR_SET_PDEATHSIG = 1
    ctypes.CDLL("libc.so.6", use_errno=True).prctl(PR_SET_PDEATHSIG,
                                                   signal.SIGKILL)


def _run_bounded(cmd: list) -> None:
    """Run gem5 with a wall-clock timeout, killing the whole process group on
    expiry so a runaway/livelock can't fill the disk with O3PipeView trace.

    `start_new_session` puts gem5 in its own group (pgid == pid) so the timeout
    kill reaps any children too; `_set_pdeathsig` covers the orphan case where
    the parent dies first. Mirrors `subprocess.run(check=True, capture_output)`:
    raises CalledProcessError on nonzero exit (with bytes out/err, as before).
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=str(GEM5_DIR), start_new_session=True,
                            preexec_fn=_set_pdeathsig)
    try:
        out, err = proc.communicate(timeout=GEM5_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise RuntimeError(
            f"gem5 timed out after {GEM5_TIMEOUT_S}s (runaway/livelock) — killed")
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, out, err)


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


def parse_lsq(trace_path: Path) -> Dict[int, List[dict]]:
    """Parse a LSQUnit debug trace into per-PC load-event records.

    The O3PipeView destructor doesn't run for in-flight speculative loads (the
    LSQ keeps a reference until simulation end), so those loads never emit
    pipeview lines. The LSQUnit debug trace logs every load as it enters,
    executes, and exits the LSQ — capturing the cache-touch signal that
    pipeview hides.

    Returns dict pc → list of {sn, insert_tick, execute_tick, squash_tick,
    packet_tick, spec_read_tick, expose_tick}.
    expose_tick > 0 → InvisiSpec issued a cache-modifying validate/expose for
    this load at its visibility point (the real transmit; 0 on non-InvisiSpec
    builds, which never emit the line). check_ld_invisispec keys its leak
    verdict on this tick.
    A load with execute_tick > 0 issued a memory request at the TOP of the load
    path (pre-defense); a load with squash_tick > 0 was squashed. The cache-fate
    fields disambiguate what "Executing load" actually did downstream:
      packet_tick    > 0 → a real read packet went to cache (visible leak)
      spec_read_tick > 0 → sent only as an invisible spec read (no visible fill)
      both 0 (executed) → bounced (delay_unit) before any packet — no cache touch
    These come from the same LSQUnit debug flag (lsq_unit.hh), so they are already
    in the trace; check_ld uses them as a secondary cache-reach gate on its hits.
    """
    by_pc: Dict[int, List[dict]] = defaultdict(list)
    by_sn: Dict[int, dict] = {}
    insert_re  = re.compile(r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+Inserting load PC \(0x([0-9a-f]+)=>")
    execute_re = re.compile(r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+Executing load PC \(0x([0-9a-f]+)=>")
    squash_re  = re.compile(r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+Load Instruction PC \(0x([0-9a-f]+)=>.*squashed,\s*\[sn:(\d+)\]")
    packet_re  = re.compile(r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+successfully sent out packet\(s\) for inst \[sn:(\d+)\]")
    spec_re    = re.compile(r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+send a spec read for inst \[sn:(\d+)\]")
    # [InvisiSpec] the cache-MODIFYING access (expose/validate) issued at the
    # load's visibility point — distinct from the invisible spec read above.
    # Only InvisiSpec traces emit this; a no-op (field stays 0) on other builds.
    expose_re  = re.compile(r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+Validate/Expose request for inst \[sn:(\d+)\]")
    # [SpecLFB / newer gem5 base] the load's actual cache access. This base has no
    # "successfully sent out packet(s)" line; instead LSQUnit::read() logs this
    # right before issuing the request, and ONLY when the load is NOT store-forwarded
    # (lsq_unit.cc:1766). So memaccess_tick>0 ⇒ the load went to cache. Separate
    # field (does not touch packet_tick) so existing checkers are unaffected.
    memaccess_re = re.compile(r"^\s*(\d+):\s+system\.cpu\.iew\.lsq\..*:\s+Doing memory access for inst \[sn:(\d+)\]")
    # [SpecLFB / Cache debug flag] the L1D outcome of the load's access. In the
    # trace a load logs "Doing memory access for inst [sn:N]" and then, on the
    # next dcache line (same tick), the cache reports "access for ReadReq
    # [a:b] hit ..." or "... miss". A MISS installs a (secret-dependent) line in
    # L1 = the real cache-state perturbation the UV6 channel needs; a HIT on a
    # pre-warmed constant line changes no tag state (the const-addr
    # over-approximation). So we pair each memaccess [sn:N] with the FOLLOWING
    # ReadReq outcome and record cache_fill_tick (set only on a MISS = install).
    # Loads = ReadReq (stores = WriteReq, ignored). No-op on builds without the
    # Cache flag (the field stays 0). Pairing is conservative: a missed pairing
    # leaves cache_fill_tick=0 (treated as no-install).
    dcache_read_re = re.compile(
        r"^\s*(\d+):\s+system\.cpu\.dcache:\s+access for ReadReq \[[0-9a-f]+:[0-9a-f]+\]\s+(hit|miss)")
    pending_read_sn = None  # sn of the last load memaccess awaiting its ReadReq outcome
    # [SpecLFB] per-load USL classification while branches are unresolved
    # (Speclfb debug flag). isCUSL=1 ⇒ the load IS a conditional unsafe spec
    # load (should be protected); isUnsafe=0 on such a load ⇒ SpecLFB left it
    # UNPROTECTED (the UV6 first-spec-load exemption — its line installs in L1,
    # vs an isUnsafe=1 load whose fill is held in the LFB). Sets spec_cusl /
    # spec_unprotected; only SpecLFB emits these lines (no-op elsewhere).
    speclfb_usl_re = re.compile(
        r"^\s*(\d+):.*Initiating Translation inst \[sn:(\d+)\] sPC [0-9a-f]+ - "
        r"Prior Brs Not Resolved\. isCUSL: ([01])\..*?isUnsafe: ([01])")
    insert_sn_re  = re.compile(r"\[sn:(\d+)\]")
    with open(trace_path) as f:
        for line in f:
            m = insert_re.match(line)
            if m:
                tick = int(m.group(1)); pc = int(m.group(2), 16)
                sn_m = insert_sn_re.search(line)
                sn = int(sn_m.group(1)) if sn_m else -1
                rec = dict(pc=pc, sn=sn, insert_tick=tick, execute_tick=0,
                           squash_tick=0, packet_tick=0, spec_read_tick=0,
                           expose_tick=0, memaccess_tick=0, cache_fill_tick=0,
                           cache_access_outcome="",
                           spec_cusl=False, spec_unprotected=False)
                by_sn[sn] = rec
                by_pc[pc].append(rec)
                continue
            m = execute_re.match(line)
            if m:
                tick = int(m.group(1)); pc = int(m.group(2), 16)
                sn_m = insert_sn_re.search(line)
                sn = int(sn_m.group(1)) if sn_m else -1
                rec = by_sn.get(sn)
                if rec is not None:
                    rec["execute_tick"] = tick
                continue
            m = packet_re.match(line)
            if m:
                rec = by_sn.get(int(m.group(2)))
                if rec is not None and rec["packet_tick"] == 0:
                    rec["packet_tick"] = int(m.group(1))
                continue
            m = spec_re.match(line)
            if m:
                rec = by_sn.get(int(m.group(2)))
                if rec is not None and rec["spec_read_tick"] == 0:
                    rec["spec_read_tick"] = int(m.group(1))
                continue
            m = expose_re.match(line)
            if m:
                rec = by_sn.get(int(m.group(2)))
                if rec is not None and rec["expose_tick"] == 0:
                    rec["expose_tick"] = int(m.group(1))
                continue
            m = memaccess_re.match(line)
            if m:
                sn = int(m.group(2))
                rec = by_sn.get(sn)
                if rec is not None and rec["memaccess_tick"] == 0:
                    rec["memaccess_tick"] = int(m.group(1))
                pending_read_sn = sn  # its ReadReq outcome is the next dcache line
                continue
            m = dcache_read_re.match(line)
            if m and pending_read_sn is not None:
                rec = by_sn.get(pending_read_sn)
                if rec is not None and rec["cache_access_outcome"] == "":
                    rec["cache_access_outcome"] = m.group(2)
                    if m.group(2) == "miss":        # miss → L1 fill/install
                        rec["cache_fill_tick"] = int(m.group(1))
                pending_read_sn = None
                continue
            m = speclfb_usl_re.match(line)
            if m:
                rec = by_sn.get(int(m.group(2)))
                if rec is not None and m.group(3) == "1":   # isCUSL: genuine USL
                    rec["spec_cusl"] = True
                    if m.group(4) == "0":                   # isUnsafe=0: not protected
                        rec["spec_unprotected"] = True
                continue
            m = squash_re.match(line)
            if m:
                tick = int(m.group(1)); pc = int(m.group(2), 16); sn = int(m.group(3))
                rec = by_sn.get(sn)
                if rec is not None:
                    rec["squash_tick"] = tick
    return dict(by_pc)


_COMMIT_SQUASH_RE = re.compile(
    r"^\s*(\d+):\s+system\.cpu\.commit.*Squashing due to branch mispred PC:(0x[0-9a-f]+)")


def parse_commit_squashes(trace_path: Path) -> Dict[int, List[int]]:
    """Parse Commit-debug 'Squashing due to branch mispred PC:<pc>' events.

    Returns dict pc -> sorted list of ticks at which the branch at <pc>
    broadcast its misprediction squash — i.e. the observable fetch redirect.
    A delay-based defense (STT implicit-channel "made pending") lets a tainted
    branch RESOLVE in-window but never broadcasts its squash in-window, so the
    branch's pc has no in-window entry here. check_br keys the leak on this tick
    (not the pipeview 'complete' tick), which is why it needs the Commit trace.
    """
    by_pc: Dict[int, List[int]] = defaultdict(list)
    with open(trace_path) as f:
        for line in f:
            m = _COMMIT_SQUASH_RE.match(line)
            if m:
                by_pc[int(m.group(2), 16)].append(int(m.group(1)))
    return {pc: sorted(t) for pc, t in by_pc.items()}


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


# ── Panic → hit reclassification ────────────────────────────────────────────
#
# An idivq with divisor=0 raises Divide-Error. The fact that the fault fired
# (vs. silently completing) is itself a side-channel: it reveals the
# divisor's zero-ness. When the divide is the test's xmit *and* lives on the
# BTB-forced speculative shadow, the fault is the leak signal we're trying
# to measure — but gem5's O3 model panics on the fault before the squash
# arrives, so process_one() would normally bucket it as `status="error"`.
#
# Codegen guarantees: non-xm divs route through %rcx with `orq $1, %rcx`,
# so they cannot fault. Architectural xm divs (xm PC ≤ any mispredict
# branch PC) are real program crashes and stay as errors. Only speculative
# xm-div panics are promoted to `issued_in_window=True`.

_DIVIDE_FAULT_RE = re.compile(
    r"panic:\s+fault\s+\(Divide-Error\).*?PC\s*\(0x([0-9a-f]+)",
    re.IGNORECASE,
)


def _alloy_pc_at_offset(parts: dict, offset: int) -> Optional[int]:
    """Map an x86 byte offset (relative to the litmus function base) back to
    the Alloy PC whose marker region contains it.

    Markers come from the .ann.json: each annotation has x86_pc_offset for
    its branch_pc; commit_boundary entries and xmit have x86_offset.
    """
    pc_offs: Dict[int, int] = {}
    for a in parts.get("annotations", []):
        pc = a.get("branch_pc")
        off = a.get("x86_pc_offset")
        if pc is not None and off is not None:
            pc_offs[pc] = off
    for which in (parts.get("lc"), parts.get("fnc"), parts.get("xmit")):
        if which:
            pc = which.get("pc")
            off = which.get("x86_offset")
            if pc is not None and off is not None:
                pc_offs[pc] = off
    if not pc_offs:
        return None
    sorted_pcs = sorted(pc_offs.items(), key=lambda kv: kv[1])
    for i, (pc, off) in enumerate(sorted_pcs):
        next_off = sorted_pcs[i + 1][1] if i + 1 < len(sorted_pcs) else 1 << 30
        if off <= offset < next_off:
            return pc
    return None


def classify_divide_panic(stderr: str, parts: dict, xmit_pc: Optional[int],
                          xmit_kind: str) -> Optional[dict]:
    """If `stderr` is a Divide-Error panic on the xm div sitting in the
    speculative shadow, return a dict of fields to merge into the per-test
    result (turning the error into a hit). Otherwise return None.
    """
    if not xmit_pc or xmit_kind != "other_x":
        return None
    m = _DIVIDE_FAULT_RE.search(stderr)
    if not m:
        return None
    fault_addr = int(m.group(1), 16)
    xmit_x86_off = parts.get("xmit", {}).get("x86_offset")
    if xmit_x86_off is None:
        return None
    base = xmit_pc - xmit_x86_off
    fault_off = fault_addr - base
    fault_pc = _alloy_pc_at_offset(parts, fault_off)
    xmit_alloy_pc = parts.get("xmit", {}).get("pc")
    if fault_pc is None or fault_pc != xmit_alloy_pc:
        return None
    mispredict_pcs = [a.get("branch_pc") for a in parts.get("annotations", [])
                      if a.get("mode") in ("mispredict_not_taken",
                                           "mispredict_taken")
                      and a.get("branch_pc") is not None]
    if not mispredict_pcs or xmit_alloy_pc <= min(mispredict_pcs):
        return None
    return dict(
        status="ok",
        issued_in_window=True,
        hit_kind="div_fault",
        error=None,
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
    out: List[dict] = []
    base = None  # lazily resolved if any legacy entry needs it
    for e in ann_full.get("annotations", []):
        stall = int(e.get("resolve_stall_cycles", 0) or 0)
        if stall <= 0:
            continue
        # New schema: absolute branch_addr.
        addr = e.get("branch_addr")
        if addr is None:
            # Backward-compat with legacy ann.json files.
            bxo = e.get("x86_branch_offset")
            if bxo is None:
                continue
            if base is None:
                base = _func_base_addr(binary, func_name)
                if base is None:
                    return out
            addr = base + int(bxo)
        out.append(dict(pc=int(addr), stall_cycles=stall))
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
#   check_fn(by_pc, xmit_pc, lc_pc, fnc_pc, unresolved, ticks_per_cycle,
#            lsq_by_pc, squash_by_pc) → dict with at least "issued_in_window"
# `lsq_by_pc` is the LSQUnit-debug-trace mapping (pc → list of load events)
# so check_ld can use the LSQ "Executing load" tick — the real cache-touch
# signal — for speculative loads that pipeview omits.
# `squash_by_pc` is the Commit-debug mapping (pc → list of mispredict-squash
# broadcast ticks) so check_br can key the leak on the actual redirect tick.
CheckFn = Callable[[Dict[int, list], Optional[int], Optional[int], Optional[int],
                    List[dict], int, Dict[int, list], Dict[int, list]], dict]


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
    parts: dict = {}
    xmit_pc: Optional[int] = None
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
            by_pc     = parse_pipeview(trace)
            lsq_by_pc = parse_lsq(trace)
            squash_by_pc = parse_commit_squashes(trace)
            ticks_per_cycle = parse_ticks_per_cycle(workdir / "m5out")
            unresolved = collect_unresolved_branches(
                dict(annotations=parts["annotations"]), binary, name)
            # The xmit PC, if itself an annotated unresolved branch, is the
            # event we're conditioning on — exclude it from the bound check.
            unresolved = [u for u in unresolved if u["pc"] != xmit_pc]
            check_result = check_fn(by_pc, xmit_pc, lc_pc, fnc_pc,
                                    unresolved, ticks_per_cycle, lsq_by_pc,
                                    squash_by_pc)
            result.update(check_result)

    except subprocess.CalledProcessError as e:
        result["status"] = "error"
        stderr = (e.stderr or b"").decode(errors="replace")
        # gem5 aborts dump a libc/python backtrace whose tail is useless; the
        # actual cause is the "panic:"/"fatal:" line near the top. Surface it.
        cause = next((ln.strip() for ln in stderr.splitlines()
                      if ln.startswith(("panic:", "fatal:"))), None)
        result["error"] = (cause + " | " if cause else "") + stderr[-400:]
        # Promote speculative-shadow div-by-zero panics on the xm to hits:
        # the fault firing is the leak signal. See classify_divide_panic.
        hit = classify_divide_panic(stderr, parts, xmit_pc,
                                    result.get("xmit_kind", ""))
        if hit is not None:
            result.update(hit)
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
