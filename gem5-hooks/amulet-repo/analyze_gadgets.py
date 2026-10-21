#!/usr/bin/env python3
"""
Static speculative-transmitter-gadget analyzer for AMuLeT/revizor test cases.

PURELY STATIC: decodes the already-assembled flat binary (.o) of each test with
iced-x86, builds its CFG, enumerates every control-flow path, and on each path
(a straight-line instruction stream) runs a register/flag def-use (taint) pass +
a critical-path latency schedule. No execution / Unicorn / gem5 / contract.

A test "has a gadget" if ANY real CFG path exhibits one. Working per-path (rather
than in raw program order) makes the dataflow EXACT and rejects chains that span
mutually-exclusive branch arms (which can never co-execute).

Two gadget shapes (Anna's definition), with the full minimal-backbone filters:

  LL  (load->load, `ld`):  a conditional branch (speculation source), then a
      secret load into a register, then a later load whose ADDRESS index register
      is reg-chained from that secret load.
  BRX (branch-in-branch, `br_x`):  an inner conditional branch whose FLAGS are
      reg-chained from a load (= the transmitter), nested under an OUTER
      conditional branch that comes before the secret load.

Filters (all required unless toggled off):
  - register dependency chain secret-load -> transmitter (the taint pass);
  - PATH validity: branch, secret-load and transmitter on one CFG path (inherent
    to per-path analysis);
  - WINDOW: the source/outer branch RESOLVES later than the transmitter acts
    (LL: load touches cache; BRX: inner branch resolves) -- measured by the
    latency schedule, so the branch must be slow-to-resolve (load-dependent);
  - BRX outer branch is itself a speculation primitive covering the inner branch;
  - UNPROTECTED exclusion: reject if the secret-load's dest reg was already loaded
    (committed-path) before the branch -> secret available without speculation;
  - FENCE exclusion: reject if a serializing insn (LFENCE/MFENCE/CPUID) sits
    between the branch and the transmitter on the path -> speculation blocked.

WINDOW MODEL: infinite-width OoO critical path, per path. Architectural inputs
ready at cycle 0; value ready = max(input ready) + latency; LOAD_LAT models a
(potentially missing) load. A branch resolves at its flag-input ready cycle; a
load accesses the cache at its address-ready cycle. Latencies are CLI-tunable.

Usage:
  python analyze_gadgets.py <dir-with-test_case_*.o> [--json out] [-v]
       [--load-lat N] [--alu-lat N] [--loose] [--allow-unprotected]
       [--allow-fenced] [--max-paths N]
"""
import sys
import glob
import os
import json
import argparse
import iced_x86 as ic

FC = ic.FlowControl
_R, _W, _RW = ic.OpAccess.READ, ic.OpAccess.WRITE, ic.OpAccess.READ_WRITE
_CR, _CW = ic.OpAccess.COND_READ, ic.OpAccess.COND_WRITE
READS = {_R, _RW, _CR}
WRITES = {_W, _RW, _CW}
BARRIERS = {ic.Mnemonic.LFENCE, ic.Mnemonic.MFENCE, ic.Mnemonic.CPUID}

NON_SECRET = {ic.Register.R14, ic.Register.RSP, ic.Register.RBP,
              ic.Register.RIP, ic.Register.NONE}

LOAD_LAT = 100
ALU_LAT = 1
BR_LAT = 1


def _full(reg):
    if reg == ic.Register.NONE:
        return ic.Register.NONE
    if not ic.RegisterExt.is_gpr(reg):
        return None
    return ic.RegisterExt.full_register(reg)


class Insn:
    __slots__ = ("idx", "ip", "text", "reads", "writes", "addr_regs", "is_load",
                 "is_store", "flags_read", "flags_written", "is_jcc", "is_jmp",
                 "is_ret", "is_barrier", "target_ip")

    def __init__(self, idx, ins, info, fmt):
        self.idx = idx
        self.ip = ins.ip
        self.text = fmt.format(ins)
        fc = ins.flow_control
        self.is_jcc = fc == FC.CONDITIONAL_BRANCH
        self.is_jmp = fc == FC.UNCONDITIONAL_BRANCH
        self.is_ret = fc in (FC.RETURN, FC.INTERRUPT)
        self.is_barrier = ins.mnemonic in BARRIERS
        self.target_ip = (ins.near_branch_target
                          if (self.is_jcc or self.is_jmp) else None)
        self.flags_read = ins.rflags_read != 0
        self.flags_written = ins.rflags_written != 0
        reads, writes = set(), set()
        for u in info.used_registers():
            f = _full(u.register)
            if f is None:
                continue
            if u.access in READS:
                reads.add(f)
            if u.access in WRITES:
                writes.add(f)
        addr_regs, is_load, is_store = set(), False, False
        for m in info.used_memory():
            for r in (m.base, m.index):
                f = _full(r)
                if f is not None and r not in NON_SECRET:
                    addr_regs.add(f)
            if m.access in READS:
                is_load = True
            if m.access in WRITES:
                is_store = True
        self.reads = {r for r in reads if r not in NON_SECRET}
        self.writes = {r for r in writes if r not in NON_SECRET}
        self.addr_regs = addr_regs
        self.is_load = is_load
        self.is_store = is_store


def decode(path):
    data = open(path, "rb").read()
    dec = ic.Decoder(64, data, ip=0x401000)
    fac = ic.InstructionInfoFactory()
    fmt = ic.Formatter(ic.FormatterSyntax.INTEL)
    insns, addr2idx = [], {}
    for ins in dec:
        if ins.code == ic.Code.INVALID:
            break
        addr2idx[ins.ip] = len(insns)
        insns.append(Insn(len(insns), ins, fac.info(ins), fmt))
    return insns, addr2idx


def successors(insns, addr2idx):
    succ = {}
    n = len(insns)
    for i, ins in enumerate(insns):
        nxt = i + 1 if i + 1 < n else None
        if ins.is_jcc:
            t = addr2idx.get(ins.target_ip)
            succ[i] = [x for x in (nxt, t) if x is not None]
        elif ins.is_jmp:
            t = addr2idx.get(ins.target_ip)
            succ[i] = [t] if t is not None else []
        elif ins.is_ret:
            succ[i] = []
        else:
            succ[i] = [nxt] if nxt is not None else []
    return succ


def enum_paths(succ, n, cap):
    """All entry->sink paths through the (acyclic) CFG, capped."""
    paths = []
    stack = [(0, [0], {0})]
    while stack:
        node, path, seen = stack.pop()
        outs = succ.get(node, [])
        outs = [s for s in outs if s not in seen]
        if not outs:
            paths.append(path)
            if len(paths) >= cap:
                break
            continue
        for s in outs:
            stack.append((s, path + [s], seen | {s}))
    return paths


def analyze_path(insns, path, loose, allow_unprotected, allow_fenced):
    """Run taint + schedule over one straight-line path; return gadgets."""
    seq = [insns[i] for i in path]
    m = len(seq)
    reg_taint = {}
    flag_taint = set()
    reg_ready = {}
    flag_ready = 0
    out_cyc = [0] * m
    access_cyc = [0] * m
    resolve_cyc = [0] * m
    cond_pos = []                  # path positions of Jcc seen so far
    last_barrier = -1             # path position of most recent barrier
    load_def_before = {}          # reg -> earliest path-pos a LOAD wrote it
    gadgets = []

    def rdy(regs):
        return max((reg_ready.get(r, 0) for r in regs), default=0)

    def viable_branches(before_pos):
        # conditional branches at path-pos < before_pos; unless --allow-fenced,
        # also require no serializing barrier between the branch and here
        # (i.e. branch is after the most-recent barrier seen so far).
        return [p for p in cond_pos
                if p < before_pos and (allow_fenced or p > last_barrier)]

    for pos, ins in enumerate(seq):
        addr_ready = rdy(ins.addr_regs)
        in_ready = rdy(ins.reads)
        flags_in_ready = flag_ready if ins.flags_read else 0
        if ins.is_load:
            access_cyc[pos] = addr_ready
            value_ready = addr_ready + LOAD_LAT
            out = max(in_ready, flags_in_ready, value_ready) + ALU_LAT
        else:
            out = max(in_ready, flags_in_ready, addr_ready) + ALU_LAT
        out_cyc[pos] = out
        if ins.is_jcc:
            resolve_cyc[pos] = flags_in_ready + BR_LAT

        in_taint = set()
        for r in ins.reads:
            in_taint |= reg_taint.get(r, set())
        addr_taint = set()
        for r in ins.addr_regs:
            addr_taint |= reg_taint.get(r, set())

        # ---- LL transmitter ----
        if ins.is_load and addr_taint:
            src_pos = min(addr_taint)             # path-pos of earliest secret load
            cands = viable_branches(src_pos)
            if cands:
                best = max(cands, key=lambda p: resolve_cyc[p])
                window = resolve_cyc[best] - access_cyc[pos]
                unprot = _preloaded(seq[src_pos], load_def_before, best)
                if (loose or window > 0) and (allow_unprotected or not unprot):
                    gadgets.append(_mk("LL", seq, best, src_pos, pos, window,
                                       resolve_cyc[best], access_cyc[pos]))

        # ---- BRX transmitter ----
        if ins.is_jcc and ins.flags_read and flag_taint:
            src_pos = min(flag_taint)
            outers = viable_branches(src_pos)
            if outers:
                best = max(outers, key=lambda p: resolve_cyc[p])
                window = resolve_cyc[best] - resolve_cyc[pos]
                unprot = _preloaded(seq[src_pos], load_def_before, best)
                if (loose or window > 0) and (allow_unprotected or not unprot):
                    gadgets.append(_mk("BRX", seq, best, src_pos, pos, window,
                                       resolve_cyc[best], resolve_cyc[pos]))

        # ---- update state ----
        if ins.flags_written:
            ft = set(in_taint)
            if ins.is_load:
                ft.add(pos)
            flag_taint = ft
            flag_ready = out
        if ins.writes:
            if ins.is_load:
                for r in ins.writes:
                    reg_taint[r] = {pos}
                    reg_ready[r] = out
                    load_def_before.setdefault(r, pos)
            else:
                for r in ins.writes:
                    if in_taint:
                        reg_taint[r] = set(in_taint)
                    else:
                        reg_taint.pop(r, None)
                    reg_ready[r] = out
        if ins.is_barrier:
            last_barrier = pos
        if ins.is_jcc:
            cond_pos.append(pos)

    return gadgets


def _preloaded(src_ins, load_def_before, branch_pos):
    """secret reg of src loaded by a load BEFORE the branch on this path?"""
    for r in src_ins.writes:
        p = load_def_before.get(r)
        if p is not None and p < branch_pos:
            return True
    return False


def _mk(kind, seq, bpos, src_pos, xmit_pos, window, b_cyc, x_cyc):
    g = {"type": kind, "secret_load": seq[src_pos].idx,
         "transmitter": seq[xmit_pos].idx, "window_cycles": window,
         "evidence": {"secret_load": seq[src_pos].text,
                      "transmitter": seq[xmit_pos].text}}
    if kind == "LL":
        g["branch"] = seq[bpos].idx
        g["branch_resolve_cycle"] = b_cyc
        g["xmit_access_cycle"] = x_cyc
        g["evidence"]["branch"] = seq[bpos].text
    else:
        g["outer_branch"] = seq[bpos].idx
        g["outer_resolve_cycle"] = b_cyc
        g["xmit_resolve_cycle"] = x_cyc
        g["evidence"]["outer_branch"] = seq[bpos].text
    return g


def analyze(insns, addr2idx, loose=False, allow_unprotected=False,
            allow_fenced=False, max_paths=4096):
    succ = successors(insns, addr2idx)
    paths = enum_paths(succ, len(insns), max_paths)
    seen, gadgets = set(), []
    for p in paths:
        for g in analyze_path(insns, p, loose, allow_unprotected, allow_fenced):
            key = (g["type"], g.get("branch", g.get("outer_branch")),
                   g["secret_load"], g["transmitter"])
            if key not in seen:
                seen.add(key)
                gadgets.append(g)
    return gadgets


def main():
    global LOAD_LAT, ALU_LAT
    ap = argparse.ArgumentParser()
    ap.add_argument("indir")
    ap.add_argument("--json")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--load-lat", type=int, default=LOAD_LAT)
    ap.add_argument("--alu-lat", type=int, default=ALU_LAT)
    ap.add_argument("--loose", action="store_true",
                    help="disable the window check (structure only)")
    ap.add_argument("--allow-unprotected", action="store_true",
                    help="keep gadgets whose secret reg was loaded before the branch")
    ap.add_argument("--allow-fenced", action="store_true",
                    help="keep gadgets with a fence between branch and transmitter")
    ap.add_argument("--max-paths", type=int, default=4096)
    args = ap.parse_args()
    LOAD_LAT, ALU_LAT = args.load_lat, args.alu_lat

    objs = sorted(glob.glob(os.path.join(args.indir, "*.o")))
    if not objs:
        sys.exit(f"no .o files in {args.indir}")

    results = []
    n_ll = n_brx = n_either = 0
    for obj in objs:
        try:
            insns, addr2idx = decode(obj)
            gadgets = analyze(insns, addr2idx, loose=args.loose,
                              allow_unprotected=args.allow_unprotected,
                              allow_fenced=args.allow_fenced,
                              max_paths=args.max_paths)
        except Exception as e:
            results.append({"test": os.path.basename(obj), "error": str(e)})
            continue
        has_ll = any(g["type"] == "LL" for g in gadgets)
        has_brx = any(g["type"] == "BRX" for g in gadgets)
        n_ll += has_ll
        n_brx += has_brx
        n_either += (has_ll or has_brx)
        results.append({"test": os.path.basename(obj),
                        "has_LL": has_ll, "has_BRX": has_brx, "gadgets": gadgets})
        if args.verbose and gadgets:
            print(f"\n## {os.path.basename(obj)}")
            for g in gadgets:
                ev = g["evidence"]
                if g["type"] == "LL":
                    print(f"  LL  win={g['window_cycles']:>4}c "
                          f"(br@{g['branch_resolve_cycle']} > xmit@{g['xmit_access_cycle']}): "
                          f"[{g['branch']}] {ev['branch']} -> "
                          f"[{g['secret_load']}] {ev['secret_load']} -reg-> "
                          f"[{g['transmitter']}] {ev['transmitter']}")
                else:
                    print(f"  BRX win={g['window_cycles']:>4}c "
                          f"(outer@{g['outer_resolve_cycle']} > inner@{g['xmit_resolve_cycle']}): "
                          f"[{g['outer_branch']}] {ev['outer_branch']} -> "
                          f"[{g['secret_load']}] {ev['secret_load']} -reg-> "
                          f"[{g['transmitter']}] {ev['transmitter']}")

    N = len(objs)
    mode = "LOOSE" if args.loose else f"window(load_lat={LOAD_LAT})"
    extra = []
    if args.allow_unprotected:
        extra.append("allow-unprotected")
    if args.allow_fenced:
        extra.append("allow-fenced")
    print(f"\n=== {N} test cases | path-based | {mode}"
          f"{' | ' + ','.join(extra) if extra else ''} ===")
    print(f"  LL  (load->load   ld  gadget): {n_ll:5d}  ({100*n_ll/N:.1f}%)")
    print(f"  BRX (branch-in-br br_x gadget): {n_brx:5d}  ({100*n_brx/N:.1f}%)")
    print(f"  either                        : {n_either:5d}  ({100*n_either/N:.1f}%)")

    if args.json:
        with open(args.json, "w") as f:
            json.dump({"params": {"load_lat": LOAD_LAT, "alu_lat": ALU_LAT,
                                  "loose": args.loose,
                                  "allow_unprotected": args.allow_unprotected,
                                  "allow_fenced": args.allow_fenced},
                       "summary": {"n": N, "LL": n_ll, "BRX": n_brx,
                                   "either": n_either}, "tests": results}, f, indent=1)
        print(f"  -> {args.json}")


if __name__ == "__main__":
    main()
