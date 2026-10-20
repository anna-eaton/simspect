#!/usr/bin/env python3
"""OTB (recon getOldestTaint) leak checker on /work/gem5-recon-modded (scheme2 + allow_leaked).

Gadget (from STT_6_otb2.als): xmit load address ← a 2-input ALU fed by two loads la (under an
early-resolving correctly-not-taken branch) + lb (under a late mispredict branch `bb`). recon's
getOldestTaint pins the ALU taint to the OLDER la; when la's branch resolves, freeTaints clears the
ALU taint even though lb is still speculative → the xmit issues & accesses cache with a
secret(lb)-dependent address.

LEAK CRITERION (the OTB-correct window, which check_ld's (lc,fnc) window does NOT capture):
    the xmit LOAD issues + accesses cache (Executing-load tick) BEFORE lb's branch `bb` broadcasts
    its squash (i.e. while lb is still speculative). Under correct STT the xmit's address is tainted
    (lb speculative) and must NOT touch cache until bb resolves.

Timing: la's branch (correctly-not-taken) resolves AFTER the ALU executes (so getOldestTaint pins to
la while it's tainted) but well BEFORE bb; bb (mispredict) gets a large stall so lb stays speculative.

Usage: python3 otb_check.py [N] [pc0_stall] [bb_stall]
"""
import os, sys, json, tempfile, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.update(
    SIMSPECT_GEM5_BIN="/work/gem5-recon-modded/build/X86/gem5.opt", SIMSPECT_GEM5_DIR="/work/gem5-recon-modded",
    SIMSPECT_SE_CONFIG="/work/gem5-recon-modded/configs/example/se.py", SIMSPECT_GEM5_CPU="X86O3CPU",
    SIMSPECT_GEM5_DBG_FLAG="O3PipeView,LSQUnit,Commit", SIMSPECT_ALLOW_LEAKED="1",
    SIMSPECT_BRANCH_ANN_ENABLE="1", SIMSPECT_GEM5_TIMEOUT_S="120")
sys.path.insert(0, str(ROOT / "STAGE3_gem5"))
import gem5_common as g
g._scheme = 2

TS = ROOT / "testsets/STT_6_otb2/mispredict_not_taken"


def check(stem, pc0_stall, bb_stall):
    ann = json.load(open(TS / "ann" / f"{stem}.ann.json"))
    for a in ann["annotations"]:
        a["resolve_stall_cycles"] = pc0_stall if a["mode"] == "correctly_not_taken" else bb_stall
    wd = Path(tempfile.mkdtemp(prefix="otb_"))
    ap = wd / f"{stem}.ann.json"
    ap.write_text(json.dumps(ann))
    binary = g.build_binary(TS / "asm" / f"{stem}.s", wd)
    xp = g.resolve_pc(binary, stem, ann["xmit"])
    if xp is None:
        return None
    tr = g.run_gem5(binary, wd, ann_path=ap)
    txt = Path(tr).read_text(errors="ignore")
    by = g.parse_pipeview(tr)
    xr = (by.get(xp, [{}]) or [{}])[0]
    xissue = xr.get("issue") or 0
    # xmit cache-access ticks (LSQUnit "Executing load" at the xmit PC)
    xtouch = sorted(int(l.split(":")[0]) for l in txt.splitlines()
                    if "Executing load" in l and hex(xp)[2:] in l.lower())
    # bb = the mispredict branch; its squash broadcast = lb-resolution. (Earliest non-startup squash.)
    sq = g.parse_commit_squashes(tr)
    bb_squash = sorted(t for pc, ts in sq.items() if pc != 0x401000 for t in ts)
    bb_tick = bb_squash[0] if bb_squash else None
    # LEAK: the xmit was RELEASED (issued+completed = obtained its data) while lb is still
    # speculative — i.e. its issue precedes lb's branch squash. (The ~2.6M "Executing load" tick
    # is a baseline speculative read present even in the control; the discriminating signal is
    # when getOldestTaint actually RELEASES the transmitter, = the issue/complete tick.)
    xcomplete = xr.get("complete") or 0
    leak = (xissue > 0 and xcomplete > 0 and bb_tick is not None and xissue < bb_tick)
    return dict(xissue=xissue, xcomplete=xcomplete, xtouch=xtouch[:2], bb_squash=bb_tick, leak=leak)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    pc0 = int(sys.argv[2]) if len(sys.argv) > 2 else 2500
    bb = int(sys.argv[3]) if len(sys.argv) > 3 else 9000
    stems = sorted(p.stem for p in (TS / "asm").glob("inst-*.s"))[:n]
    print(f"# OTB getOldestTaint DIFFERENTIAL on /work/gem5-recon-modded scheme2+allow_leaked")
    print(f"# {len(stems)} gadgets. OTB timing: la-branch={pc0}, lb-branch(bb)={bb} (la resolves first).")
    print(f"# CONTROL: both branches={bb} (la & lb resolve together → getOldestTaint frees both).")
    print(f"# LEAK = xmit accesses cache while lb speculative in OTB timing but NOT in control\n")
    leaks = usable = 0
    for stem in stems:
        try:
            otb  = check(stem, pc0, bb)        # la resolves first
            ctl  = check(stem, bb,  bb)        # la & lb resolve together (control)
        except Exception as e:
            print(f"{stem}: ERR {type(e).__name__}: {str(e)[:70]}"); continue
        if otb is None or ctl is None:
            print(f"{stem}: no xmit pc"); continue
        usable += 1
        # LEAK (robust differential): getOldestTaint RELEASES the xmit EARLIER under OTB
        # timing (when the OLDER la resolves) than under the control (where la & lb resolve
        # together, so the xmit is held to ~lb-resolve). A clear margin (1 cycle = 500 ticks)
        # rules out the tick-level boundary case where the control xmit issues right at
        # resolution. Both runs must obtain data (issue+complete).
        MARGIN = 500
        oi, ci = otb["xissue"], ctl["xissue"]
        leak = (oi > 0 and otb["xcomplete"] > 0 and ci > 0
                and oi + MARGIN < ci                         # released earlier under OTB timing
                and otb["bb_squash"] is not None and oi < otb["bb_squash"])  # while lb still speculative
        if leak:
            leaks += 1
        print(f"{stem}: OTB[issue={oi} bb={otb['bb_squash']}] CTL[issue={ci}]  Δrelease={ci-oi if (oi and ci) else '?'} "
              f"{'<<< LEAK' if leak else ''}")
    print(f"\n# {leaks}/{usable} OTB gadgets LEAK differentially (getOldestTaint early-free: leak only when la resolves first)")


if __name__ == "__main__":
    main()
