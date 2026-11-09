#!/usr/bin/env python3
"""
_fv2_slice.py: shared static helpers for the fanout-v2 FP diagnostics (bucket-fv2, 2026-11-09).
Not a diagnostic itself (bucket_hits.py only discovers diag_*.py).

transmitter_slice(stem, mode_dir) = backward register slice from the transmitter over the
linear litmus body of <mode_dir>/asm/<stem>.s, exactly the rule of the bug agent's
/tests/simspect_alloy_20261108/bugwork/fp_hits/bucket_fp.py (bug-investigate-fp, which produced
the S1-on-E3/E4 and R-SA-13 verdicts): ld = the registers of the transmitter's memory operand;
br_x = the source of the `movq %src,%rcx` that feeds the compare. The walk follows register
defs backwards, stops at a load (that load is a "producer"; SSE if its destination is an xmm),
ignores stores, compares and jumps, and treats non-mov ops as reading their destination.
Returns {"xmms": [...], "producers": [...], "xmm4": bool, "sse_producer": bool, "slice": [...]}
or {"err": ...}.

twin_held(stem, mode, kind) = the same stem+mode did NOT hit in the GPR-only twin campaign
(STT_6_fv2, same row). Reads diagnostics/twin_fv2/<mode>/<kind>/window-results.json, a verbatim
copy of the twin campaign's file. Unknown twin -> None (callers then do not bucket).
"""
import json, re, functools
from pathlib import Path

HERE = Path(__file__).resolve().parent
R32 = {"eax": "rax", "ebx": "rbx", "ecx": "rcx", "edx": "rdx", "esi": "rsi", "edi": "rdi", "esp": "rsp", "ebp": "rbp",
       "ax": "rax", "al": "rax", "cl": "rcx", "cx": "rcx", "dl": "rdx", "dx": "rdx", "sil": "rsi", "dil": "rdi", "bl": "rbx"}


def _norm(r):
    r = r.lstrip("%")
    m = re.match(r"(r\d+)[dwb]$", r)
    if m:
        return m.group(1)
    return R32.get(r, r)


def _split_ops(s):
    ops, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        if ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            ops.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        ops.append(cur.strip())
    return ops


def _parse_body(path, stem):
    n = stem.split("-")[1]
    lines, on, cur_pc = [], False, None
    for ln in open(path):
        t = ln.split("#")[0].strip()
        m = re.match(rf"__litmus_inst_{n}_pc(\d+):", t)
        if m:
            on = True; cur_pc = int(m.group(1)); continue
        if not on:
            continue
        if t.startswith(".cfi_endproc"):
            break
        if t.startswith("retq"):
            on = False; continue
        if not t or t.endswith(":") or t.startswith("."):
            continue
        parts = t.split(None, 1)
        lines.append((cur_pc, parts[0], _split_ops(parts[1]) if len(parts) > 1 else []))
    return lines


def _regs_in(op):
    return [_norm(x) for x in re.findall(r"%(\w+)", op)]


def _is_mem(op):
    return "(" in op and not op.startswith("$")


@functools.lru_cache(maxsize=None)
def transmitter_slice(stem, mode_dir):
    mode_dir = Path(mode_dir)
    try:
        ann = json.loads((mode_dir / "ann" / f"{stem}.ann.json").read_text())
        body = _parse_body(mode_dir / "asm" / f"{stem}.s", stem)
    except OSError as e:
        return {"err": f"{type(e).__name__}: {e}"}
    kind = ann.get("xmit", {}).get("kind")
    xpc = ann["xmit"]["pc"]
    idx = [i for i, l in enumerate(body) if l[0] == xpc]
    if not idx:
        return {"err": "no xmit label"}
    i0 = idx[0]
    need = set()
    if kind == "ld":
        for op in body[i0][2]:
            if _is_mem(op):
                need |= set(_regs_in(op[op.index("("):]))
    elif kind == "br_x":
        pc, mn, ops = body[i0]
        if mn.startswith("mov") and len(ops) == 2:
            need = set(_regs_in(ops[0]))
        else:
            return {"err": f"br_x first instruction not a 2-operand mov: {mn}"}
    else:
        return {"err": f"kind {kind} not handled"}
    need -= {"rsp", "rbp"}
    slice_instrs, producers = [], []
    for j in range(i0 - 1, -1, -1):
        pc, mn, ops = body[j]
        if not ops or mn.startswith("j") or mn.startswith("cmp") or mn.startswith("test"):
            continue
        dst = ops[-1]
        if _is_mem(dst):
            continue
        d = _regs_in(dst)
        if not d or d[0] not in need:
            continue
        dreg = d[0]
        srcops = ops[:-1]
        slice_instrs.append((pc, mn, ops))
        need.discard(dreg)
        zero_idiom = mn in ("pxor", "xorq", "xorl", "xorps") and len(ops) == 2 and _norm(ops[0]) == dreg
        if any(_is_mem(o) for o in srcops) and not mn.startswith("lea"):
            producers.append({"pc": pc, "mn": mn, "dst": dreg, "sse": dreg.startswith("xmm"),
                              "asm": f"{mn} {', '.join(ops)}"})
            continue
        if zero_idiom:
            continue
        for o in srcops:
            if o.startswith("$"):
                continue
            need |= set(_regs_in(o))
        if not (mn.startswith("mov") or mn.startswith("lea")):
            need.add(dreg)
        need -= {"rsp", "rbp"}
    xmms = sorted({r for (_, _, ops) in slice_instrs for o in ops for r in _regs_in(o) if r.startswith("xmm")},
                  key=lambda x: int(x[3:]))
    return {"kind": kind, "xmms": xmms, "producers": producers, "xmm4": "xmm4" in xmms,
            "sse_producer": any(p["sse"] for p in producers),
            "slice": [f"pc{pc}: {mn} {', '.join(ops)}" for (pc, mn, ops) in reversed(slice_instrs)]}


@functools.lru_cache(maxsize=None)
def _twin(mode, kind):
    p = HERE / "twin_fv2" / mode / kind / "window-results.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    recs = data if isinstance(data, list) else (data.get("results") or list(data.values()))
    return {r["name"].split("__")[0]: (bool(r.get("issued_in_window")), r.get("status")) for r in recs if isinstance(r, dict)}


def twin_held(stem, mode, kind):
    """True = twin ran ok and did not hit; False = twin hit; None = unknown (no twin record / error)."""
    t = _twin(mode, kind)
    if t is None or stem not in t:
        return None
    hit, status = t[stem]
    if hit:
        return False
    return True if status == "ok" else None


def mode_dir_of(xml_dir, mode):
    # abspath, not resolve(): testsets_twostage/<t>/xml is a symlink to a shared xml dir
    import os
    return str(Path(os.path.abspath(str(xml_dir))).parent / mode)


def kind_of(stem, mode_dir):
    try:
        return json.loads((Path(mode_dir) / "ann" / f"{stem}.ann.json").read_text())["xmit"]["kind"]
    except (OSError, KeyError, ValueError):
        return None
