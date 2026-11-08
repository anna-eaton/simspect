#!/usr/bin/env python3
"""Why is a transmitter's operand public under SPT? x86-level slice (2026-11-07).

For a test's compiled .s, follows the Alloy-order path (entry, bb_1 ... the xmit
block) and builds a value graph of every register write. Then it applies
gem5-spt's taint rules to that graph and reports whether the xmit's leakage
operand (br_x: the flags its jcc reads; ld, str: its address registers) is public,
and why.

gem5-spt rules used (source lines read 2026-11-07, /work/gem5-spt/src/cpu/o3):
  taint     a load's destination is always tainted; any other instruction's
            destination is tainted iff one of its sources is
            (rob_impl.hh:236-250); immediates and xor-zero idioms are clean.
  VP        a load or store that reaches the visibility point untaints its
            tainted address registers (lsq_unit_impl.hh:1185-1207,1262-1279;
            cpu.cc:2132). In Spectre mode the VP is "every older branch
            resolved" (rob_impl.hh:556-560), so here: memory ops before the
            first unresolved branch in Alloy order.
  fwd       a non-transmitter whose sources are all clean gets a clean
            destination (rob_impl.hh:800, fwdUntaint=1).
  bwd       mov with a clean destination cleans its source; add/sub/adc/sbb
            with a clean destination and exactly one tainted source clean
            that source (rob_impl.hh:853-878, bwdUntaint=1).
freeParam (untaints per cycle) and timing are not modelled: this says what
SPT's rules make public eventually, and gem5's own "made pending" line (see
spt_taint_probe.py) says whether it was public at the squash.

Verdicts: const (public without any untaint), declassified (public only
through VP untaint by a non-speculative memory op, listed), tainted (still
tainted by these rules), unknown (an instruction the slicer does not model).

    python3 spt_cond_slice.py <testdir>/<mode> inst-1 inst-2 ... --out slice.json
"""
import argparse, json, re
from pathlib import Path

_R64 = {}
for a, b in [("ax", "rax"), ("bx", "rbx"), ("cx", "rcx"), ("dx", "rdx"), ("si", "rsi"), ("di", "rdi"),
             ("bp", "rbp"), ("sp", "rsp")]:
    for f in (f"r{a}", f"e{a}", a):
        _R64[f] = b
for n in range(8, 16):
    for f in (f"r{n}", f"r{n}d", f"r{n}w", f"r{n}b"):
        _R64[f] = f"r{n}"
for f, b in [("al", "rax"), ("bl", "rbx"), ("cl", "rcx"), ("dl", "rdx"), ("sil", "rsi"), ("dil", "rdi")]:
    _R64[f] = b
_PUBLIC_INIT = {"rsp", "rbp"}
_MEM = re.compile(r"(-?[\w$]*)\((%\w+)?(?:,(%\w+))?(?:,(\d))?\)")
_BLOCK = re.compile(r"^(?:\.LBB\d+_\d+:|# %bb\.\d+:)\s*#\s*%(\S+)")
_LABEL = re.compile(r"^__litmus_\w+_pc(\d+):")
_JCC = re.compile(r"^j(?!mp)[a-z]+$")
_ALU2 = {"add", "sub", "and", "or", "xor", "adc", "sbb", "imul"}
_ALU1 = {"not", "neg", "inc", "dec"}
_SHIFT = {"shl", "shr", "sar", "sal", "rol", "ror"}


def _reg(tok):
    tok = tok.strip()
    if tok.startswith("%"):
        return _R64.get(tok[1:], tok[1:])
    return None


def _split_ops(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _mem_regs(op):
    m = _MEM.search(op)
    if not m:
        return None
    return [r for r in (_reg(m.group(2)) if m.group(2) else None, _reg(m.group(3)) if m.group(3) else None) if r]


def _blocks(s_text):
    """[(block_name, [(alloy_pc_label_or_None, line)])] in file order, comments stripped."""
    blocks, cur, name, pc = [], [], "entry", None
    started = False
    for raw in s_text.splitlines():
        line = raw.split("#")[0].strip()
        bm = _BLOCK.match(raw.strip())
        if bm:
            blocks.append((name, cur)); cur = []; name = bm.group(1); continue
        if raw.strip().startswith('"inst-') or raw.strip().startswith("inst-"):
            started = True; continue
        if not started:
            continue
        if raw.strip().startswith(".Lfunc_end"):
            break
        lm = _LABEL.match(raw.strip())
        if lm:
            pc = int(lm.group(1)); cur.append(("label", pc)); continue
        if not line or line.startswith(".") or line.startswith("#") or line.endswith(":"):
            continue
        cur.append(("ins", line.strip()))
    blocks.append((name, cur))
    return blocks


def _path(blocks, xmit_pc):
    keep = [b for b in blocks if b[0] == "entry" or re.fullmatch(r"bb_\d+", b[0])]
    keep.sort(key=lambda b: -1 if b[0] == "entry" else int(b[0][3:]))
    seq, pc = [], None
    for _, items in keep:
        for kind, v in items:
            if kind == "label":
                pc = v; continue
            seq.append((pc, v))
            if pc == xmit_pc and _JCC.match(v.split()[0]):
                return seq
    return seq


def analyze(s_path, ann):
    xmit = ann["xmit"]; xpc = xmit["pc"]; kind = xmit.get("kind")
    unres = sorted(e["branch_pc"] for e in ann.get("annotations", [])
                   if e.get("mode") != "correctly_not_taken" and e.get("branch_pc") != xpc)
    first_unres = unres[0] if unres else None
    seq = _path(_blocks(Path(s_path).read_text()), xpc)
    nodes = []                      # value nodes
    cur = {}                        # arch reg -> node id
    flags = None                    # node id of last flags writer
    mem_ops = []                    # (alloy_pc, idx, op, [addr node ids])
    unknown = []

    def val(r):
        if r not in cur:
            nodes.append(dict(kind="init_public" if r in _PUBLIC_INIT else "init", reg=r, srcs=[]))
            cur[r] = len(nodes) - 1
        return cur[r]

    def new(kind, srcs, line, pc, reg=None):
        nodes.append(dict(kind=kind, srcs=srcs, line=line, pc=pc, reg=reg))
        return len(nodes) - 1

    xmit_ops = None
    for i, (pc, line) in enumerate(seq):
        parts = line.split(None, 1)
        mn = parts[0]; ops = _split_ops(parts[1]) if len(parts) > 1 else []
        base = re.sub(r"[bwlq]$", "", mn) if mn not in ("mfence", "nop", "cqto", "retq") else mn
        if mn in ("mfence", "nop", "lfence", "sfence"):
            continue
        if _JCC.match(mn):
            if pc == xpc and kind == "br_x":
                xmit_ops = [flags]
            continue
        if mn in ("jmp", "jmpq", "retq", "callq", "pushq", "popq"):
            continue
        if base == "mov" and len(ops) == 2:
            src, dst = ops
            if "(" in dst:                                   # store
                ar = _mem_regs(dst) or []
                ids = [val(r) for r in ar]
                mem_ops.append((pc, i, "store", ids))
                if pc == xpc and kind == "str":
                    xmit_ops = ids
                continue
            d = _reg(dst)
            if src.startswith("$"):
                cur[d] = new("const", [], line, pc, d)
            elif "(" in src:                                 # load
                ar = _mem_regs(src) or []
                ids = [val(r) for r in ar]
                mem_ops.append((pc, i, "load", ids))
                cur[d] = new("load", ids, line, pc, d)
                if pc == xpc and kind == "ld":
                    xmit_ops = ids
            else:
                cur[d] = new("mov", [val(_reg(src))], line, pc, d)
            continue
        if base == "lea" and len(ops) == 2:
            ar = _mem_regs(ops[0]) or []
            d = _reg(ops[1]); cur[d] = new("alu", [val(r) for r in ar], line, pc, d)
            continue
        if base in ("test", "cmp") and len(ops) == 2:
            srcs = [val(_reg(o)) for o in ops if _reg(o)]
            flags = new("alu", srcs, line, pc, "flags")
            continue
        if base == "xor" and len(ops) == 2 and _reg(ops[0]) and _reg(ops[0]) == _reg(ops[1]):
            d = _reg(ops[1]); cur[d] = new("const", [], line, pc, d); flags = cur[d]
            continue
        if base in _ALU2 and len(ops) == 2 and "(" not in line:
            d = _reg(ops[1])
            srcs = ([val(_reg(ops[0]))] if _reg(ops[0]) else []) + [val(d)]
            cur[d] = new(base, srcs, line, pc, d); flags = cur[d]
            continue
        if (base in _ALU1 or base in _SHIFT) and "(" not in line:
            d = _reg(ops[-1])
            srcs = [val(d)] + ([val("rcx")] if ops and ops[0] == "%cl" else [])
            cur[d] = new("alu", srcs, line, pc, d); flags = cur[d]
            continue
        if mn == "cqto":
            cur["rdx"] = new("alu", [val("rax")], line, pc, "rdx"); continue
        if base == "idiv" and len(ops) == 1 and _reg(ops[0]):
            srcs = [val("rax"), val("rdx"), val(_reg(ops[0]))]
            q = new("alu", srcs, line, pc, "rax"); r_ = new("alu", srcs, line, pc, "rdx")
            cur["rax"], cur["rdx"] = q, r_
            continue
        unknown.append(line)
    if unknown:
        return dict(verdict="unknown", unknown=unknown)
    if xmit_ops is None:
        return dict(verdict="unknown", unknown=["xmit operand not found on the Alloy path"])
    if any(x is None for x in xmit_ops):
        return dict(verdict="unknown", unknown=["xmit flags have no producer on the path"])

    def tainted_set(declass):
        t = {}
        for n, nd in enumerate(nodes):
            if n in declass:
                t[n] = False
            elif nd["kind"] == "load":
                t[n] = True
            elif nd["kind"] in ("const", "init_public"):
                t[n] = False
            elif nd["kind"] == "init":
                t[n] = False                                 # harness zero-init (xorl %eax + copies)
            else:
                t[n] = any(t[s] for s in nd["srcs"])
        return t

    t0 = tainted_set(set())
    base_tainted = any(t0[x] for x in xmit_ops)
    # VP untaint: memory ops before the first unresolved branch (Alloy order).
    declass, via = set(), []
    for pc, i, what, ids in mem_ops:
        if first_unres is not None and pc is not None and pc >= first_unres:
            continue
        for n in ids:
            if t0.get(n):
                declass.add(n); via.append(dict(alloy_pc=pc, op=what, line=seq[i][1], node=n))
    # bwd propagation through mov / single-tainted-src add/sub, then fwd (iterate to fixpoint).
    for _ in range(len(nodes)):
        t = tainted_set(declass)
        grew = False
        for n, nd in enumerate(nodes):
            if t[n]:
                continue
            if nd["kind"] == "mov" and t[nd["srcs"][0]] and nd["srcs"][0] not in declass:
                declass.add(nd["srcs"][0]); grew = True
            elif nd["kind"] in ("add", "sub", "adc", "sbb"):
                ts = [s for s in nd["srcs"] if t[s]]
                if len(ts) == 1 and n in declass and ts[0] not in declass:
                    declass.add(ts[0]); grew = True
        if not grew:
            break
    t = tainted_set(declass)
    public = not any(t[x] for x in xmit_ops)
    leaves = sorted({nodes[s]["line"] for s in _cone(nodes, xmit_ops) if nodes[s]["kind"] == "load"})
    verdict = "const" if not base_tainted else ("declassified" if public else "tainted")
    return dict(verdict=verdict, first_unresolved_pc=first_unres, load_sources=leaves,
                declassified_by=via if verdict == "declassified" else [],
                path=[f"pc{pc}: {ln}" for pc, ln in seq if not re.match(r"movq\s+\$0, \d+\(%rsp\)", ln)])


def _cone(nodes, roots):
    seen, st = set(), list(roots)
    while st:
        n = st.pop()
        if n in seen:
            continue
        seen.add(n)
        if nodes[n]["kind"] != "load":
            st.extend(nodes[n]["srcs"])
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("testdir", type=Path)
    ap.add_argument("stems", nargs="+")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    res = {}
    for st in a.stems:
        ann = json.loads((a.testdir / "ann" / f"{st}.ann.json").read_text())
        try:
            res[st] = analyze(a.testdir / "asm" / f"{st}.s", ann)
        except Exception as e:
            res[st] = dict(verdict="unknown", unknown=[f"{type(e).__name__}: {e}"])
        print(st, res[st]["verdict"], res[st].get("load_sources"), [d["line"] for d in res[st].get("declassified_by", [])],
              res[st].get("unknown"))
    if a.out:
        a.out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
