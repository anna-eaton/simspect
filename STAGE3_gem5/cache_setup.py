#!/usr/bin/env python3
"""
cache_setup.py: initial cache-state strategies for a litmus test (Stage-3 harness glue).

Run-config knob `gem5.cache_setup` (env SIMSPECT_CACHE_SETUP, bridged by
pipeline._build_gem5_env), default `warm`. Documented in
wiki/design/SIMSPECT_HOOKS.md "Cache setup strategies".

Why: Stage 2 emits a prologue that zero-fills every sandbox array with stores and
then an `mfence` barrier (parsexml.py "Prologue -> test region barrier"), so every
sandbox line is hot in L1D when the test region starts. A strategy rewrites the
.s right after that barrier, before the first test instruction:

  warm  today's behavior. The .s is not touched; process_one calls
        gem5_common.build_binary exactly as before (byte-identical binary).
  cold  clflush every cache line of the test function's data region (its whole
        stack frame: allocas, red zone, saved registers, return address; plus any
        rip-relative global, of which today's corpora have none -> refused), then
        `mfence`. General: the region comes from the function's prologue, never
        from the transmitter or any one instruction.

  random  (2026-11-09, Anna: the default for CleanupSpec and SpecLFB only) each test
        runs warm or cold, chosen per test by choose(stem, seed): a hash of
        (gem5.cache_setup_seed -> SIMSPECT_CACHE_SETUP_SEED, default DEFAULT_SEED, test
        stem). Deterministic: re-running one test by hand with the same seed gives the
        same choice (`python3 cache_setup.py choose <stem> [--seed S]` prints it). Each
        record carries the strategy actually used (`cache_setup`), plus
        `cache_setup_mode: "random"` and `cache_setup_seed`. Refused wherever cold is.

Adding a strategy = one function `payload(frame) -> list[str]` in STRATEGIES.

The inserted code uses only `disp(%rsp)` / `disp(%rbp)` operands, so it clobbers
no register; clflush and mfence do not write flags. Inserting bytes shifts every
later PC, so the annotation is re-resolved (remap_annotation) and verified:
the code before the insertion is unchanged, the code after it is the same
instruction stream shifted by one constant, every __litmus_* label moved by that
constant, and every annotation address (any `addr` / `*_addr` field, the same
field set make_rmw_corpus.addr_fields walks) lands on the same instruction. Any
deviation raises CacheSetupError (the record errors; nothing is guessed).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

_S2 = str(Path(__file__).resolve().parent.parent / "STAGE2_compilation")
if _S2 not in sys.path:
    sys.path.append(_S2)
from make_rmw_corpus import addr_fields, key_paths  # noqa: E402  (reuse, not a copy)

LINE = 64
DEFAULT = "warm"
BEGIN_LABEL = "__simspect_cachesetup_begin"
END_LABEL = "__simspect_cachesetup_end"


class CacheSetupError(RuntimeError):
    pass


def current() -> str:
    return (os.environ.get("SIMSPECT_CACHE_SETUP") or DEFAULT).strip().lower()


# ── .s analysis ──────────────────────────────────────────────────────────────

def _code(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _safe(stem: str) -> str:
    return stem.replace("-", "_").replace(".", "_")


def find_barrier(lines: List[str], stem: str) -> int:
    """Index of the line AFTER the prologue barrier's `#NO_APP` (the insertion point).

    The barrier is the only `mfence` between the function label and the first
    __litmus_<stem>_* label (parsexml.py emits exactly one there)."""
    fstart = next((i for i, l in enumerate(lines) if _code(l) == f'"{stem}":'), None)
    if fstart is None:
        raise CacheSetupError("function label not found")
    first_lab = next((i for i in range(fstart, len(lines))
                      if re.match(rf"^__litmus_{re.escape(_safe(stem))}_\w+:$", lines[i].strip())),
                     None)
    if first_lab is None:
        raise CacheSetupError("no __litmus_ label")
    mf = [i for i in range(fstart, first_lab) if _code(lines[i]) == "mfence"]
    if len(mf) != 1:
        raise CacheSetupError(f"expected 1 prologue mfence, found {len(mf)}")
    j = mf[0] + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines) or lines[j].strip() != "#NO_APP":
        raise CacheSetupError("prologue mfence not closed by #NO_APP")
    return j + 1


_MEM_RE = re.compile(r"(-?\d+)?\(%(rsp|rbp)(?:,|\))")


def frame_region(lines: List[str], stem: str, insert_at: int) -> dict:
    """The test function's stack data region, relative to %rsp or %rbp at the barrier.

    Two prologue shapes occur (clang, all corpora checked 2026-11-08):
      A  push %rbp; mov %rsp,%rbp; push*P; and $-A,%rsp; sub $N,%rsp
         -> base rbp, region [-(8P + A-1 + N), +16)  (covers locals, the
            realignment gap, saved regs, saved rbp and the return address)
      B  push*P [; sub $N,%rsp]   (leaf; locals may live in the red zone)
         -> base rsp, region [lo, N + 8P + 8), lo = -128 if any negative
            rsp displacement is used (red zone), else 0.
    Any other rsp write before the barrier raises. Every direct rsp/rbp memory
    operand in the function must lie inside the region, else raises."""
    fstart = next(i for i, l in enumerate(lines) if _code(l) == f'"{stem}":')
    fend = next((i for i in range(fstart, len(lines)) if lines[i].strip().startswith(".Lfunc_end")),
                len(lines))
    pushes_before_fp = pushes_after_fp = 0
    fp = False
    align = 0
    sub = 0
    for l in lines[fstart + 1:insert_at]:
        s = _code(l)
        if not s or s.startswith(".") or s.endswith(":"):
            continue
        if s.startswith("pushq"):
            if fp:
                pushes_after_fp += 1
            else:
                pushes_before_fp += 1
            continue
        if re.fullmatch(r"movq\s+%rsp,\s*%rbp", s):
            if pushes_before_fp != 1:
                raise CacheSetupError("frame pointer set up after != 1 push")
            fp = True
            continue
        m = re.fullmatch(r"andq\s+\$-(\d+),\s*%rsp", s)
        if m:
            align = int(m.group(1))
            continue
        m = re.fullmatch(r"subq\s+\$(\d+),\s*%rsp", s)
        if m:
            sub += int(m.group(1))
            continue
        if re.search(r",\s*%(rsp|esp|rbp|ebp)$", s) or s.startswith(("popq", "leave", "call")):
            raise CacheSetupError(f"unexpected stack-pointer write before barrier: {s!r}")
    disps = {"rsp": [], "rbp": []}
    rip = []
    for l in lines[fstart + 1:fend]:
        s = _code(l)
        if "(%rip)" in s:
            rip.append(s)
        for m in _MEM_RE.finditer(s):
            disps[m.group(2)].append(int(m.group(1) or 0))
    if rip:
        raise CacheSetupError(f"rip-relative data reference not supported: {rip[0]!r}")
    if fp:
        if align and align & (align - 1):
            raise CacheSetupError(f"odd stack alignment {align}")
        lo = -(8 * pushes_after_fp + max(align - 1, 0) + sub)
        reg = dict(base="rbp", lo=lo, hi=16, shape="A_frame_pointer",
                   pushes=pushes_after_fp, align=align, sub=sub)
        if align:   # rsp = ((rbp - 8P) & -A) - sub: rsp operands must stay in [rsp, rsp+sub)
            bad = [d for d in disps["rsp"] if not 0 <= d < sub]
        else:       # rsp = rbp - 8P - sub exactly: check rsp operands relative to rbp
            off = -(8 * pushes_after_fp + sub)
            bad = [d for d in disps["rsp"] if not lo <= d + off < 16]
        if bad:
            raise CacheSetupError(f"rsp displacement outside the frame: {bad[:3]}")
        bad = [d for d in disps["rbp"] if not lo <= d < 16]
        if bad:
            raise CacheSetupError(f"rbp displacement outside the frame: {bad[:3]}")
    else:
        if disps["rbp"]:
            raise CacheSetupError("rbp-relative operand without a frame pointer")
        hi = sub + 8 * pushes_before_fp + 8
        lo = -128 if any(d < 0 for d in disps["rsp"]) else 0
        bad = [d for d in disps["rsp"] if not lo <= d < hi]
        if bad:
            raise CacheSetupError(f"rsp displacement outside the frame: {bad[:3]}")
        reg = dict(base="rsp", lo=lo, hi=hi, shape="B_no_frame_pointer",
                   pushes=pushes_before_fp, align=0, sub=sub)
    return reg


def line_probe_offsets(lo: int, hi: int) -> List[int]:
    """Offsets o in [lo, hi) such that every 64-byte line overlapping [base+lo, base+hi)
    contains some base+o, whatever the (unknown) alignment of base: hi-1, hi-1-64, ..., and lo."""
    offs, o = [], hi - 1
    while o > lo:
        offs.append(o)
        o -= LINE
    offs.append(lo)
    return sorted(set(offs))


# ── strategies (registry) ────────────────────────────────────────────────────

def _cold_burst(frame: dict) -> List[str]:
    """All clflushes back to back, then mfence. Fewer instructions than `cold`, but it
    panics CleanupSpec's Ruby with L2_TBEs=2 (see _cold); use only where smoke-tested."""
    b = frame["base"]
    return [f"\tclflush\t{o}(%{b})" for o in line_probe_offsets(frame["lo"], frame["hi"])] + \
           ["\tmfence"]


PACE_LEAS = 64   # dependent 1-cycle leas between two clflushes (cold)


def _cold(frame: dict) -> List[str]:
    """clflush every frame line, one clflush in flight at a time, then mfence.

    Paced because back-to-back flushes break CleanupSpec's Ruby MESI_Two_Level with
    L2_TBEs=2 (panic "Invalid L1 forwarded request type" when a PUTFLUSH meets a
    Resource Stall; smoke 2026-11-08), and because with ample TBEs a burst can still
    find the L2 copy mid-writeback (M_I). The same paced code runs on every build so
    cold means the same thing everywhere. Each clflush's address
    depends on %rax = 0 loaded AFTER the previous clflush's mfence, through a chain of
    PACE_LEAS dependent `leaq (%rax,%rax), %rax` (still 0; lea writes no flags).
    %rax is saved to / restored from a .bss slot outside the stack frame (that
    slot's line is hot afterwards; it is not sandbox data)."""
    b = frame["base"]
    out = ["\t.pushsection .bss", "\t.p2align 6", "__simspect_cs_save:", "\t.zero 64",
           "__simspect_cs_zero:", "\t.zero 64", "\t.popsection",
           "\tmovq\t%rax, __simspect_cs_save(%rip)"]
    for o in line_probe_offsets(frame["lo"], frame["hi"]):
        out.append("\tmovq\t__simspect_cs_zero(%rip), %rax")
        out += ["\tleaq\t(%rax,%rax), %rax"] * PACE_LEAS
        out += [f"\tclflush\t{o}(%{b},%rax)", "\tmfence"]
    out += ["\tmovq\t__simspect_cs_save(%rip), %rax", "\tmfence"]
    return out


# name -> payload(frame) -> asm lines (inserted between BEGIN/END labels).
# A third strategy (e.g. `l1_evicted`: out of L1D, still in L2) is one function here.
STRATEGIES: Dict[str, Callable[[dict], List[str]]] = {
    "cold": _cold,
    "cold_burst": _cold_burst,
}
# Meta-strategies: resolved per test to a concrete one ("warm" or a STRATEGIES key).
RANDOM_CHOICES = ("warm", "cold")
META = ("random",)
KNOWN = ("warm",) + tuple(STRATEGIES) + META
# Default seed for `random` (run config gem5.cache_setup_seed overrides it). Changing it
# changes which tests run cold, so it is part of a campaign's provenance (manifest + records).
DEFAULT_SEED = "simspect-cache-random-v1"


def current_seed() -> str:
    return (os.environ.get("SIMSPECT_CACHE_SETUP_SEED") or DEFAULT_SEED).strip()


def choose(stem: str, seed: Optional[str] = None) -> str:
    """`random`'s per-test choice: warm or cold from sha256(f"{seed}\\0{stem}").

    Keyed on the test stem only (never on a sweep grid point, worker or time), so every
    grid point of one test, a rerun, and a by-hand reproduction get the same choice. A
    `__<suffix>` (the repo's per-variant record-name convention, e.g. `<stem>__sw_<idx>`;
    bucket_hits.py and the evidence scripts split on it too) is dropped first."""
    import hashlib
    stem = str(stem).split("__")[0]
    seed = current_seed() if seed is None else str(seed)
    h = hashlib.sha256(f"{seed}\0{stem}".encode()).digest()
    return RANDOM_CHOICES[h[0] & 1]


def resolve(strategy: str, stem: str, seed: Optional[str] = None) -> str:
    """Concrete strategy for one test (identity except for the META strategies)."""
    return choose(stem, seed) if strategy == "random" else strategy

# Builds whose clflush does not flush (smoke 2026-11-08,
# STAGE3_gem5/triage/cache_setup_20261108/smoke_cache_setup.py; table in
# wiki/design/SIMSPECT_HOOKS.md "Cache setup strategies"). A clflush-based strategy is
# refused there instead of silently running warm. Key = substring of the gem5 binary path.
CLFLUSH_UNSUPPORTED = {
    "amulet-gem5-InvisiSpec_AE": "Ruby MESI_Two_Level ignores clflush (no CleanInvalidReq->FLUSH "
                                 "conversion in RubyPort; no Ruby request, L1D misses unchanged)",
    "amulet-gem5-STT_AE": "Ruby MESI_Two_Level ignores clflush (same as InvisiSpec)",
    "gem5-recon-ruby3": "Ruby MESI_Three_Level ignores clflush (first access after it hits M in L0)",
    "gem5-spt": "panics: commit_impl.hh:1610 assertion srcRegTaintVec != nullptr at the clflush",
}


def check_build(strategy: str, gem5_bin: str) -> None:
    if strategy in ("cold", "cold_burst", "random"):   # random runs cold on ~half the tests
        for key, why in CLFLUSH_UNSUPPORTED.items():
            if key in str(gem5_bin):
                raise CacheSetupError(f"cache_setup={strategy} unsupported on {gem5_bin}: {why}")


def transform_asm(text: str, stem: str, strategy: str) -> Tuple[str, dict]:
    if strategy not in STRATEGIES:
        raise CacheSetupError(f"unknown cache_setup {strategy!r} (known: {', '.join(KNOWN)})")
    lines = text.split("\n")
    at = find_barrier(lines, stem)
    frame = frame_region(lines, stem, at)
    payload = STRATEGIES[strategy](frame)
    block = ([f"\t# simspect cache_setup={strategy} (STAGE3_gem5/cache_setup.py)", "\t#APP",
              f"{BEGIN_LABEL}:"] + payload + [f"{END_LABEL}:", "\t#NO_APP"])
    new = lines[:at] + block + lines[at:]
    n_flush = sum(1 for p in payload if "clflush" in p)
    return "\n".join(new), dict(strategy=strategy, frame=frame, n_clflush=n_flush,
                                n_payload_instrs=sum(1 for p in payload if not
                                                     p.strip().startswith(".") and
                                                     not p.strip().endswith(":")))


# ── annotation re-resolution + verification ─────────────────────────────────

def _nm(binary: Path) -> Dict[str, int]:
    out = subprocess.check_output(["nm", "--defined-only", str(binary)], text=True)
    syms = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3:
            syms[p[2]] = int(p[0], 16)
    return syms


def _rows(binary: Path) -> List[tuple]:
    """(addr, mnemonic, operand text with direct-target annotations removed, direct target)."""
    out = subprocess.check_output(["objdump", "-d", "--no-show-raw-insn", str(binary)],
                                  text=True, stderr=subprocess.DEVNULL)
    rows = []
    for line in out.splitlines():
        m = re.match(r"^\s+([0-9a-f]+):\s+(\S+)\s*(.*)$", line)
        if not m:
            continue
        ops = m.group(3)
        t = re.match(r"([0-9a-f]+) <[^>]*>", ops)
        tgt = int(t.group(1), 16) if t else None
        ops = re.sub(r"\s*#.*$", "", ops) if t is None else ""
        rows.append((int(m.group(1), 16), m.group(2), ops.strip(), tgt))
    return rows


def _set_path(obj, path: str, value):
    toks = re.findall(r"\.([^.\[]+)|\[(\d+)\]", path)
    cur = obj
    for k, i in toks[:-1]:
        cur = cur[k] if k else cur[int(i)]
    k, i = toks[-1]
    if k:
        cur[k] = value
    else:
        cur[int(i)] = value
    return cur, (k if k else None)


def remap_annotation(ann: dict, old_bin: Path, new_bin: Path, stem: str) -> Tuple[dict, dict]:
    so, sn = _nm(old_bin), _nm(new_bin)
    if BEGIN_LABEL not in sn or END_LABEL not in sn:
        raise CacheSetupError("insertion labels missing from the new binary")
    begin, end = sn[BEGIN_LABEL], sn[END_LABEL]
    delta = end - begin
    ro, rn = _rows(old_bin), _rows(new_bin)
    pre_o = [r for r in ro if r[0] < begin]
    pre_n = [r for r in rn if r[0] < begin]
    mid = [r for r in rn if begin <= r[0] < end]
    post_o = [r for r in ro if r[0] >= begin]
    post_n = [r for r in rn if r[0] >= end]
    shift = lambda a: a + delta if a >= begin else a  # noqa: E731
    if pre_o != pre_n:
        raise CacheSetupError("code before the insertion point changed")
    if len(post_o) != len(post_n):
        raise CacheSetupError("instruction count after the insertion point changed")
    for a, b in zip(post_o, post_n):
        if (b[0], b[1], b[2]) != (a[0] + delta, a[1], a[2]) or \
           (a[3] is not None and b[3] != shift(a[3])):
            raise CacheSetupError(f"non-constant shift at {a[0]:#x}: {a} -> {b}")
    lab_o = {k: v for k, v in so.items() if k.startswith(f"__litmus_{_safe(stem)}_")}
    lab_n = {k: v for k, v in sn.items() if k.startswith(f"__litmus_{_safe(stem)}_")}
    if set(lab_o) != set(lab_n) or any(lab_n[k] != shift(v) for k, v in lab_o.items()):
        raise CacheSetupError("a __litmus_ label did not move by the insertion length")
    if so.get(stem) != sn.get(stem):
        raise CacheSetupError("function base changed")
    starts = {r[0] for r in ro}
    new = json.loads(json.dumps(ann))
    fields = addr_fields(ann)
    moved = 0
    for path, v in fields.items():
        if path == ".func_base_addr":
            continue
        if v >= begin:
            if v not in starts:
                raise CacheSetupError(f"{path}={v:#x} is not an instruction start")
            nv = v + delta
            parent, key = _set_path(new, path, nv)
            hk = "addr_hex" if key == "addr" else f"{key}_hex"
            if isinstance(parent, dict) and hk in parent:
                parent[hk] = hex(nv)
            moved += 1
    for k in ("x86_offset",):
        if k in json.dumps(ann):
            raise CacheSetupError("legacy x86_offset annotations are not supported")
    if key_paths(new) != key_paths(ann):
        raise CacheSetupError("annotation field set changed")
    # Verify: every remapped address points at the same instruction as before.
    rn_by = {r[0]: r for r in rn}
    ro_by = {r[0]: r for r in ro}
    nf = addr_fields(new)
    for path, v in fields.items():
        a, b = ro_by.get(v), rn_by.get(nf[path])
        if path == ".func_base_addr":
            continue
        if a is None or b is None or (a[1], a[2]) != (b[1], b[2]):
            raise CacheSetupError(f"{path}: instruction differs after remap ({a} vs {b})")
    return new, dict(begin=hex(begin), delta=delta, n_addr_fields=len(fields) - 1,
                     n_moved=moved, n_labels=len(lab_o))


# ── entry point used by gem5_common.process_one ─────────────────────────────

def prepare(s_path: Path, ann_path: Path, workdir: Path, build_fn,
            strategy: Optional[str] = None):
    """-> (binary, ann_path_to_use, info). warm: build_fn(s_path, workdir) only.

    `strategy` must be concrete (resolve() a META one first, as process_one does).
    Under a non-warm run setting (e.g. random) a test that resolved to warm is built
    exactly as in a warm run; the cache_setup_ok flag only passes build_binary's guard."""
    strategy = strategy or current()
    if strategy in META:
        raise CacheSetupError(f"prepare() needs a concrete strategy, got {strategy!r}")
    if strategy == "warm":
        if current() == "warm":
            return build_fn(s_path, workdir), ann_path, None
        return build_fn(s_path, workdir, cache_setup_ok=True), ann_path, None
    stem = s_path.stem
    text = s_path.read_text()
    new_text, info = transform_asm(text, stem, strategy)
    ref_dir = workdir / "_cache_setup_warm_ref"
    ref_dir.mkdir(exist_ok=True)
    old_bin = build_fn(s_path, ref_dir, cache_setup_ok=True)
    cs_dir = workdir / "_cache_setup_src"
    cs_dir.mkdir(exist_ok=True)
    cs_s = cs_dir / s_path.name
    cs_s.write_text(new_text)
    new_bin = build_fn(cs_s, workdir, cache_setup_ok=True)
    ann = json.loads(Path(ann_path).read_text())
    new_ann, rep = remap_annotation(ann, old_bin, new_bin, stem)
    info.update(rep)
    out = workdir / f"{stem}.cache_setup.ann.json"
    out.write_text(json.dumps(new_ann, indent=2) + "\n")
    return new_bin, out, info


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="cache_setup helpers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("choose", help="print `random`'s choice (warm|cold) for test stems")
    c.add_argument("stems", nargs="+")
    c.add_argument("--seed", default=None, help=f"default: $SIMSPECT_CACHE_SETUP_SEED or {DEFAULT_SEED}")
    a = ap.parse_args(argv)
    for s in a.stems:
        print(f"{s}\t{choose(s, a.seed)}")


if __name__ == "__main__":
    _main()
