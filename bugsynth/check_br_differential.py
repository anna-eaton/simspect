#!/usr/bin/env python3
"""Differential (non-interference) branch-channel checker — PROTOTYPE.

Design: bugsynth/BRANCH_CHANNEL_CHECK_DESIGN.md.

Frame (non-interference): a PUBLIC (untainted) branch observable must be INVARIANT to the secret.
Vary the secret; if any UNTAINTED branch's redirect/squash timing MOVES, that's a leak. A *tainted*
branch's own redirect moving is the DEFENSE working (STT delays it to hide its direction), NOT a leak
— so the observable projection is restricted to *untainted* branches. The taint gate is thus in the
observable selection, not a fragile redirect heuristic.

This covers branch-channel type B (cross-branch redirect-timing, e.g. nmosier pending-squash) and is the
extensible basis for A (direct-direction) and C (squash-order) via additional observable projections.

Secret parameterization (prototype): TAINT-FLIP. Secret-variant A = the gadget where the older branch's
condition is secret-derived (reads a speculative load → tainted); variant B = it reads a constant
(untainted). Reuses the STT_6_pendsquash / STT_6_pendsquash_ut twins. (The fully faithful VALUE-FLIP —
init the secret load's line to 0 vs 1 so the branch *direction* flips — is the documented next step; the
framework here is identical, only `run_variant`'s two inputs change.)

Taint classification per branch is from the ASM: a branch whose condition-setup reads a REGISTER (i.e. a
value from a load) is tainted; one that loads an IMMEDIATE constant is untainted. (Matches the model's
pendsquash_tainted marker but also works on base br_x gadgets where the xmit branch reads a load.)

Run on /work/stt scheme 2.   Usage: python3 check_br_differential.py [N] [keepspec_stall]
"""
import os, sys, json, tempfile, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.update(
    SIMSPECT_GEM5_BIN="/work/stt/build/X86/gem5.opt", SIMSPECT_GEM5_DIR="/work/stt",
    SIMSPECT_SE_CONFIG="/work/stt/configs/example/se.py", SIMSPECT_GEM5_CPU="DerivO3CPU",
    SIMSPECT_GEM5_DBG_FLAG="O3PipeView,LSQUnit,Commit", SIMSPECT_BRANCH_ANN_ENABLE="1",
    SIMSPECT_GEM5_TIMEOUT_S="120")
sys.path.insert(0, str(ROOT / "STAGE3_gem5"))
import gem5_common as g
g._scheme = 2


def branch_taint_from_asm(s_path: Path, safe: str):
    """Forward dataflow taint over the litmus body: a register is TAINTED iff it is (transitively)
    written by a LOAD (movq from memory). A branch is tainted iff its condition register is tainted at
    the branch. This correctly handles the xmit br_bez passthrough (`movq %reg,%tmp`) — tainted only if
    %reg traces to a load, not merely because it's a register. Returns {pc:int -> tainted:bool}.

    Taint rules (program order):
      movq <mem>(..), %dst   (source has parens = a load)        -> taint %dst
      movq $imm, %dst        / xorq %dst,%dst                    -> untaint %dst (constant/zero)
      movq %src, %dst                                            -> %dst := taint(%src)
      leaq (..regs..), %dst  / addq/subq/notq/orq/andq %.., %dst -> %dst tainted if any source reg tainted
    The branch condition is the operand of the `testq %R,%R` preceding the jcc.
    """
    lines = s_path.read_text().splitlines()
    tainted = set()           # set of currently-tainted %registers
    cur_pc = None
    out = {}

    def regs_in(s):
        return set(re.findall(r'%(\w+)', s))

    for l in lines:
        ml = re.search(rf'__litmus_{safe}_pc(\d+):', l)
        if ml:
            cur_pc = int(ml.group(1)); continue
        ls = l.strip()
        # branch condition?
        mt = re.match(r'testq\s+%(\w+),\s*%(\w+)', ls)
        if mt and cur_pc is not None:
            out[cur_pc] = (mt.group(1) in tainted)
            continue
        # movq immediate -> untaint
        mi = re.match(r'movq\s+\$[^,]+,\s*%(\w+)', ls)
        if mi:
            tainted.discard(mi.group(1)); continue
        # xorq %r,%r -> zero -> untaint
        mx = re.match(r'xorq\s+%(\w+),\s*%(\w+)', ls)
        if mx and mx.group(1) == mx.group(2):
            tainted.discard(mx.group(1)); continue
        # movq <mem>,%dst : load (source operand contains parens) -> taint dst
        mm = re.match(r'movq\s+(.+),\s*%(\w+)\s*$', ls)
        if mm and '(' in mm.group(1):
            tainted.add(mm.group(2)); continue
        # movq %src,%dst : copy taint
        mc = re.match(r'movq\s+%(\w+),\s*%(\w+)', ls)
        if mc:
            (tainted.add if mc.group(1) in tainted else tainted.discard)(mc.group(2)); continue
        # leaq/alu writing a dest: dst tainted iff any source reg tainted
        ma = re.match(r'(leaq|addq|subq|orq|andq|notq)\s+(.+),\s*%(\w+)', ls)
        if ma:
            srcs = regs_in(ma.group(2))
            dst = ma.group(3)
            (tainted.add if (srcs & tainted) else tainted.discard)(dst); continue
    return out


def _secret_value_asm(s_path: Path, secret: int, wd: Path) -> Path:
    """VALUE-FLIP: write the gadget's secret value into memory. The litmus loads read the
    zero-initialised stack region (mem_base), so the prologue `movq $0, N(%rsp)` stores ARE the
    memory init. Rewriting them to `movq $secret, N(%rsp)` makes every speculative load return
    `secret` → a TAINTED (load-fed) branch's direction flips; an UNTAINTED branch (condition is a
    register, never a load) is unaffected. So this varies ONLY the secret. secret=0 → original asm."""
    if secret == 0:
        return s_path
    out = wd / s_path.name          # keep the same stem (binary function name is looked up by stem)
    text = re.sub(r'(movq\s+)\$0(,\s*-?\d+\(%rsp\))', rf'\g<1>${secret}\g<2>', s_path.read_text())
    out.write_text(text)
    return out


def run_variant(testset: str, stem: str, keepspec_stall: int, cut: int, secret: int = 0):
    """Run one gadget on /work/stt; return per-branch observables:
       {pc -> dict(addr, tainted, made_pending, squash_tick)}.
       secret = the in-memory secret value (VALUE-FLIP); 0 = unmodified asm."""
    base = ROOT / f"testsets/{testset}/mispredict_not_taken"
    ann = json.load(open(base / "ann" / f"{stem}.ann.json"))
    for a in ann["annotations"]:
        a["resolve_stall_cycles"] = keepspec_stall if a["branch_pc"] < cut else 0
    wd = Path(tempfile.mkdtemp(prefix="brdiff_"))
    ap = wd / f"{stem}.ann.json"
    ap.write_text(json.dumps(ann))
    s_src = _secret_value_asm(base / "asm" / f"{stem}.s", secret, wd)
    binary = g.build_binary(s_src, wd)
    safe = stem.replace("-", "_")
    nm = subprocess.run(["nm", str(binary)], capture_output=True, text=True).stdout
    labs = sorted((int(m.group(1), 16), int(m.group(2)))
                  for m in re.finditer(rf'([0-9a-f]+)\s+\w+\s+__litmus_{safe}_pc(\d+)\b', nm))
    addr_by_pc = {n: a for a, n in labs}
    nexts = {labs[i][1]: (labs[i + 1][0] if i + 1 < len(labs) else labs[i][0] + 64)
             for i in range(len(labs))}
    taint = branch_taint_from_asm(base / "asm" / f"{stem}.s", safe)
    trace = g.run_gem5(binary, wd, ann_path=ap)
    txt = Path(trace).read_text(errors="ignore")
    sq = g.parse_commit_squashes(trace)            # {pc_addr -> [ticks]}
    pend_abs = set()
    for l in txt.splitlines():
        if "made pending" in l:
            m = re.search(r'PC \((0x[0-9a-f]+)', l)
            if m:
                pend_abs.add(int(m.group(1), 16))

    def in_pc(abs_pc, pc):
        lo = addr_by_pc.get(pc)
        return lo is not None and lo <= abs_pc < nexts[pc]

    out = {}
    for pc, lo in addr_by_pc.items():
        if pc not in taint:        # not a branch (no condition setup) → skip
            continue
        made_pending = any(in_pc(p, pc) for p in pend_abs)
        sqt = sorted(t for p, ts in sq.items() if in_pc(p, pc) for t in ts)
        out[pc] = dict(addr=lo, tainted=taint[pc], made_pending=made_pending,
                       squash_tick=(sqt[0] if sqt else None))
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    ks = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    mode = sys.argv[3] if len(sys.argv) > 3 else "value"     # "value" (faithful) | "taint" (proxy)
    TS = "STT_6_pendsquash"
    stems = sorted(p.stem for p in (ROOT / f"testsets/{TS}/mispredict_not_taken/asm").glob("inst-*.s"))[:n]
    print("# Differential (non-interference) branch-channel check — /work/stt scheme2")
    if mode == "value":
        print(f"# VALUE-FLIP secret param: same gadget, in-memory secret = 0 vs 1 (flips the tainted branch's direction)")
    else:
        print(f"# TAINT-FLIP secret param: tainted-bo vs untainted-bo twin")
    print(f"# observable = UNTAINTED branches' redirect timing")
    print(f"# LEAK = some UNTAINTED branch's redirect/squash timing MOVES with the secret (tainted-branch moves are the defense, not a leak)\n")
    leaks = usable = oldfp = selffail = 0
    for stem in stems:
        try:
            annA = json.load(open(ROOT / f"testsets/{TS}/mispredict_not_taken/ann/{stem}.ann.json"))
            bo = [a["branch_pc"] for a in annA["annotations"] if a.get("pendsquash_tainted")]
            cut = bo[0] if bo else annA["xmit"]["pc"]
            if mode == "value":
                oa = run_variant(TS, stem, ks, cut, secret=0)   # secret = 0
                ob = run_variant(TS, stem, ks, cut, secret=1)   # secret = 1 (flips bo's direction)
                oa2 = run_variant(TS, stem, ks, cut, secret=0)  # self-consistency
            else:
                oa = run_variant("STT_6_pendsquash", stem, ks, cut)
                ob = run_variant("STT_6_pendsquash_ut", stem, ks, cut)
                oa2 = run_variant("STT_6_pendsquash", stem, ks, cut)
        except Exception as e:
            print(f"{stem}: ERR {type(e).__name__}: {str(e)[:70]}"); continue
        usable += 1
        leak_branches, defense_branches = [], []
        for pc in sorted(set(oa) & set(ob)):
            a, b = oa[pc], ob[pc]
            if (a["made_pending"] != b["made_pending"]) or (a["squash_tick"] != b["squash_tick"]):
                (defense_branches if a["tainted"] else leak_branches).append(pc)
        # self-consistency: same secret twice must produce NO moves
        self_moves = [pc for pc in (set(oa) & set(oa2))
                      if oa[pc]["made_pending"] != oa2[pc]["made_pending"]
                      or oa[pc]["squash_tick"] != oa2[pc]["squash_tick"]]
        leak = bool(leak_branches)
        leaks += leak
        oldfp += 1 if (leak_branches or defense_branches) else 0     # old check_br: ANY branch move = "leak"
        selffail += 1 if self_moves else 0
        print(f"{stem}: LEAK(untainted moves)={['pc%d'%p for p in leak_branches]} "
              f"defense(tainted moves)={['pc%d'%p for p in defense_branches]} "
              f"self-consistent={'NO!'+str(self_moves) if self_moves else 'yes'} "
              f"{'<<< LEAK' if leak else 'safe'}")
    print(f"\n# {leaks}/{usable} gadgets LEAK (an UNTAINTED branch's redirect timing depends on the secret).")
    print(f"# No-false-positive check: OLD check_br (flags ANY branch redirect/move) would flag {oldfp}/{usable} "
          f"— the {oldfp-leaks} extra are TAINTED branches whose squash STT legitimately delays (the historical")
    print(f"#   STT br_x false positives). Our taint-gated differential reports those as DEFENSE, not leak.")
    print(f"# Self-consistency: {usable-selffail}/{usable} gadgets give identical observables when the secret is")
    print(f"#   unchanged (A vs A) → no measurement-noise false leaks.  ({selffail} self-inconsistent.)")


if __name__ == "__main__":
    main()
