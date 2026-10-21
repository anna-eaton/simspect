#!/usr/bin/env python3
"""check_br_ni.py — GENERAL non-interference branch-channel checker (mainline candidate).

Consolidates the two bugsynth prototypes (check_br_differential.py + stt_branch_soundness_audit.py)
into ONE general tool that works on ANY branch testset/model, and is the proposed replacement for the
heuristic check_br.py (BRANCH_CHANNEL_CHECK_DESIGN.md, decision #3).

WHY non-interference instead of the check_br redirect heuristic: check_br flags a branch "leak" whenever
the xmit branch redirects in the speculative window — but under a sweep stall STT *legitimately* delays a
TAINTED branch's squash to window-close, which check_br miscounts as a leak (the historical STT br_x false
positives, project_stt_branch_leak_cause). The sound test is INTERFERENCE: vary the secret and ask whether
any PUBLIC, attacker-timeable observable moves. A tainted branch's own squash moving is the defense
working; only an *untainted* (public) observable moving with the secret is a real leak.

TWO complementary observables (cover branch-channel types A/B/C from the design doc):
  (1) per-branch (made_pending, squash_tick) restricted to UNTAINTED branches  — direct-direction (A) and
      cross-branch redirect-timing (B, e.g. nmosier pending-squash).
  (2) the FULL public fetch-redirect TIMELINE = sorted multiset of every squash-broadcast tick — a
      channel-agnostic backstop that also catches squash-ORDER (C) / window-modulation (E) even when
      per-PC attribution is fuzzy.

LIVENESS GATE = a scheme-0 (Unsafe) POSITIVE CONTROL (so a SOUND verdict isn't vacuous). In a litmus
test the secret only affects the SPECULATIVE (squashed, never-committed) path, so the committed stream is
secret-invariant by design — committed-stream divergence is the wrong gate. Instead we run the SAME gadget
UNPROTECTED (scheme 0): if the public observable MOVES with the secret there, the channel provably exists
and the secret reaches the observable. Then under scheme 2 (STT) we ask whether that same observable is
now closed. This is the gold-standard differential: an unprotected control proving the channel, a protected
run showing the defense shuts it.

  SOUND  = live (scheme-0 control moves) AND the scheme-2 public observable is INVARIANT  (defense holds)
  LEAK   = live AND the scheme-2 public observable MOVES with the secret
  VACUOUS= scheme-0 control does NOT move (the secret never reached a public observable — uninformative)

Secret param = VALUE-FLIP (faithful): same binary, in-memory secret 0 vs 1 (prologue movq $0,N(%rsp) ->
movq $1,...), so every speculative load returns the secret; a load-fed branch's direction flips, a
constant-fed branch is unaffected.

Usage: python3 check_br_ni.py --model STT_6 [--testset STT_6] [--mode <branchmode>] [-n N] [--stall C]
       python3 check_br_ni.py --model STT_6_pendsquash -n 12        # the synthetic pendsquash gadgets
Defaults target the canonical base STT_6 br_x gadgets on /work/stt scheme 2.
"""
import os, sys, json, tempfile, subprocess, re, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.update(
    SIMSPECT_GEM5_BIN="/work/stt/build/X86/gem5.opt", SIMSPECT_GEM5_DIR="/work/stt",
    SIMSPECT_SE_CONFIG="/work/stt/configs/example/se.py", SIMSPECT_GEM5_CPU="DerivO3CPU",
    SIMSPECT_GEM5_DBG_FLAG="O3PipeView,Commit", SIMSPECT_BRANCH_ANN_ENABLE="1",
    SIMSPECT_GEM5_TIMEOUT_S="120")
sys.path.insert(0, str(ROOT / "STAGE3_gem5"))
import gem5_common as g
g._scheme = 2


# --- ASM taint (forward dataflow): a reg is tainted iff transitively written by a load --------------
def branch_taint_from_asm(s_path: Path, safe: str):
    lines = s_path.read_text().splitlines()
    tainted, cur_pc, out = set(), None, {}
    rin = lambda s: set(re.findall(r'%(\w+)', s))
    for l in lines:
        ml = re.search(rf'__litmus_{safe}_pc(\d+):', l)
        if ml:
            cur_pc = int(ml.group(1)); continue
        ls = l.strip()
        mt = re.match(r'testq\s+%(\w+),\s*%(\w+)', ls)
        if mt and cur_pc is not None:
            out[cur_pc] = (mt.group(1) in tainted); continue
        mi = re.match(r'movq\s+\$[^,]+,\s*%(\w+)', ls)
        if mi: tainted.discard(mi.group(1)); continue
        mx = re.match(r'xorq\s+%(\w+),\s*%(\w+)', ls)
        if mx and mx.group(1) == mx.group(2): tainted.discard(mx.group(1)); continue
        mm = re.match(r'movq\s+(.+),\s*%(\w+)\s*$', ls)
        if mm and '(' in mm.group(1): tainted.add(mm.group(2)); continue
        mc = re.match(r'movq\s+%(\w+),\s*%(\w+)', ls)
        if mc: (tainted.add if mc.group(1) in tainted else tainted.discard)(mc.group(2)); continue
        ma = re.match(r'(leaq|addq|subq|orq|andq|notq)\s+(.+),\s*%(\w+)', ls)
        if ma:
            (tainted.add if (rin(ma.group(2)) & tainted) else tainted.discard)(ma.group(3))
    return out


def _secret_value_asm(s_path: Path, secret: int, wd: Path) -> Path:
    if secret == 0:
        return s_path
    out = wd / s_path.name
    out.write_text(re.sub(r'(movq\s+)\$0(,\s*-?\d+\(%rsp\))', rf'\g<1>${secret}\g<2>', s_path.read_text()))
    return out


def _pub_obs(per, timeline):
    """The attacker-timeable PUBLIC observable: the full redirect timeline + every UNTAINTED branch's
    (made_pending, squash_tick). A tainted branch's own squash is excluded (STT may legitimately delay it)."""
    untainted = tuple(sorted((pc, per[pc]["made_pending"], per[pc]["squash_tick"])
                             for pc in per if not per[pc]["tainted"]))
    return (timeline, untainted)


def _tainted_obs(per, timeline):
    """Everything attacker-visible INCLUDING tainted-branch squashes — used only for the scheme-0
    positive control (does the secret move ANYTHING observable when unprotected?)."""
    allbr = tuple(sorted((pc, per[pc]["made_pending"], per[pc]["squash_tick"]) for pc in per))
    return (timeline, allbr)


def run_variant(base: Path, stem: str, stall: int, cut: int, secret: int, scheme: int = 2):
    """Run one gadget at the given protection scheme; return (per_branch_obs, public_timeline)."""
    g._scheme = scheme
    ann = json.load(open(base / "ann" / f"{stem}.ann.json"))
    for a in ann["annotations"]:
        a["resolve_stall_cycles"] = stall if a["branch_pc"] < cut else 0
    wd = Path(tempfile.mkdtemp(prefix="brni_"))
    ap = wd / f"{stem}.ann.json"; ap.write_text(json.dumps(ann))
    s_src = _secret_value_asm(base / "asm" / f"{stem}.s", secret, wd)
    binary = g.build_binary(s_src, wd)
    safe = stem.replace("-", "_")
    nm = subprocess.run(["nm", str(binary)], capture_output=True, text=True).stdout
    labs = sorted((int(m.group(1), 16), int(m.group(2)))
                  for m in re.finditer(rf'([0-9a-f]+)\s+\w+\s+__litmus_{safe}_pc(\d+)\b', nm))
    addr_by_pc = {n: a for a, n in labs}
    nexts = {labs[i][1]: (labs[i+1][0] if i+1 < len(labs) else labs[i][0] + 64) for i in range(len(labs))}
    taint = branch_taint_from_asm(base / "asm" / f"{stem}.s", safe)
    trace = g.run_gem5(binary, wd, ann_path=ap)
    txt = Path(trace).read_text(errors="ignore")
    sq = g.parse_commit_squashes(trace)
    pend_abs = set()
    for l in txt.splitlines():
        if "made pending" in l:
            m = re.search(r'PC \((0x[0-9a-f]+)', l)
            if m: pend_abs.add(int(m.group(1), 16))
    in_pc = lambda ap_, pc: (addr_by_pc.get(pc) is not None and addr_by_pc[pc] <= ap_ < nexts[pc])
    per = {}
    for pc in addr_by_pc:
        if pc not in taint:           # not a branch
            continue
        sqt = sorted(t for p, ts in sq.items() if in_pc(p, pc) for t in ts)
        per[pc] = dict(tainted=taint[pc], made_pending=any(in_pc(p, pc) for p in pend_abs),
                       squash_tick=(sqt[0] if sqt else None))
    # public timeline = all squash-broadcast ticks except the harness startup squash at 0x401000
    timeline = tuple(sorted(int(re.match(r'\s*(\d+):', l).group(1)) for l in txt.splitlines()
                            if "Squashing due to branch mispred" in l and "0x401000" not in l))
    return per, timeline


def eval_at(base, stem, cut, stall):
    """Run the 5-run NI protocol at one stall. Cheap path: scheme-0 control first; only spend the
    scheme-2 runs if the gadget is live. Returns (live, verdict, pub_moves, any_moves, self_ok)."""
    c0p, c0t = run_variant(base, stem, stall, cut, 0, scheme=0)
    c1p, c1t = run_variant(base, stem, stall, cut, 1, scheme=0)
    if _tainted_obs(c0p, c0t) == _tainted_obs(c1p, c1t):       # not live (scheme-0 control flat)
        return False, "VACUOUS", False, False, True
    s0p, s0t = run_variant(base, stem, stall, cut, 0, scheme=2)
    s1p, s1t = run_variant(base, stem, stall, cut, 1, scheme=2)
    s0pb, s0tb = run_variant(base, stem, stall, cut, 0, scheme=2)
    pub_moves = (_pub_obs(s0p, s0t) != _pub_obs(s1p, s1t))
    any_moves = (_tainted_obs(s0p, s0t) != _tainted_obs(s1p, s1t))
    self_ok = (_tainted_obs(s0p, s0t) == _tainted_obs(s0pb, s0tb))
    return True, ("LEAK" if pub_moves else "SOUND"), pub_moves, any_moves, self_ok


def audit_gadget(base, stem, stalls):
    """Non-interference verdict for one br_x gadget across a stall band (first live stall wins).
    Returns dict(stem, verdict, live_stall, pub_moves, any_moves, self_ok). The importable entry point
    used by both the CLI here and the `br_ni_audit.py` window-results consumer."""
    ann = json.load(open(base / "ann" / f"{stem}.ann.json"))
    bo = [x["branch_pc"] for x in ann["annotations"] if x.get("pendsquash_tainted")]
    cut = bo[0] if bo else ann["xmit"]["pc"]
    res = dict(stem=stem, verdict="VACUOUS", live_stall=None,
               pub_moves=False, any_moves=False, self_ok=True)
    for st in stalls:
        lv, vd, pm, am, so = eval_at(base, stem, cut, st)
        if lv:
            res.update(verdict=vd, live_stall=st, pub_moves=pm, any_moves=am, self_ok=so)
            break
    return res


def list_brx_stems(base):
    out = []
    for p in sorted((base / "ann").glob("inst-*.ann.json")):
        if json.load(open(p))["xmit"]["kind"] == "br_x":
            out.append(p.stem.replace(".ann", ""))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="STT_6")
    ap.add_argument("--testset", default=None, help="testset dir (default = model)")
    ap.add_argument("--mode", default="mispredict_not_taken")
    ap.add_argument("-n", type=int, default=0, help="0 = all br_x gadgets")
    ap.add_argument("--stall", type=int, default=2000)
    ap.add_argument("--sweep", action="store_true",
                    help="retry each gadget across a stall band; a gadget is live if live at ANY stall")
    ap.add_argument("--stalls", default=None, help="comma-separated stall band (implies --sweep)")
    ap.add_argument("--only", default=None, help="comma-separated stems to restrict to")
    a = ap.parse_args()
    base = ROOT / f"testsets/{a.testset or a.model}/{a.mode}"
    if a.stalls:
        stalls = [int(x) for x in a.stalls.split(",")]
    elif a.sweep:
        stalls = [500, 2000, 2500, 5000]
    else:
        stalls = [a.stall]
    stems = list_brx_stems(base)
    if a.only:
        keep = set(a.only.split(",")); stems = [s for s in stems if s in keep]
    if a.n: stems = stems[:a.n]

    print(f"# check_br_ni — NON-INTERFERENCE branch audit  (model={a.model} testset={a.testset or a.model})")
    print(f"# {len(stems)} br_x gadgets | /work/stt | VALUE-FLIP secret 0 vs 1 | stalls={stalls}")
    print(f"# liveness = scheme-0 (Unsafe) positive control moves;  verdict from scheme-2 (STT) public observable")
    print(f"# SOUND=live & scheme2-public INVARIANT   LEAK=live & scheme2-public MOVES   VACUOUS=no stall makes it live\n")
    sound = leak = vac = err = oldfp = selffail = 0
    for stem in stems:
        try:
            ann = json.load(open(base / "ann" / f"{stem}.ann.json"))
            bo = [x["branch_pc"] for x in ann["annotations"] if x.get("pendsquash_tainted")]
            cut = bo[0] if bo else ann["xmit"]["pc"]
            verdict, live_stall = "VACUOUS", None
            pub_moves = any_moves = False; self_ok = True
            for st in stalls:                                  # first stall that makes it live wins
                lv, vd, pm, am, so = eval_at(base, stem, cut, st)
                if lv:
                    verdict, live_stall, pub_moves, any_moves, self_ok = vd, st, pm, am, so
                    break
        except Exception as e:
            err += 1; print(f"{stem}: ERR {type(e).__name__}: {str(e)[:60]}"); continue
        if verdict == "VACUOUS":
            vac += 1
        elif verdict == "LEAK":
            leak += 1
        else:
            sound += 1
        oldfp += 1 if (verdict != "VACUOUS" and any_moves) else 0
        selffail += 0 if self_ok else 1
        print(f"{stem}: {verdict:7s} live_stall={live_stall} scheme2_public_moves={int(pub_moves)} "
              f"scheme2_any_moves(old_check_br)={int(any_moves)} self={'ok' if self_ok else 'NO!'}")
    tot = sound + leak
    print(f"\n# {sound}/{tot} LIVE gadgets SOUND, {leak}/{tot} LEAK   ({vac} vacuous, {err} err)")
    print(f"# OLD check_br (ANY branch redirect = leak) would flag {oldfp}/{tot} — the {oldfp-leak} extra are")
    print(f"#   tainted-branch squashes STT legitimately delays (the historical STT br_x false positives).")
    print(f"# self-consistency failures (A vs A moved): {selffail}")


if __name__ == "__main__":
    main()
