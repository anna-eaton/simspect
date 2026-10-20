#!/usr/bin/env python3
"""Differential checker for the nmosier pending-squash bug on /work/stt (STT, scheme 2).

Gadget (general, from STT_6_pendsquash.als): an OLDER tainted branch `bo` (condition fed by a
speculative load) + a YOUNGER UNTAINTED Branchx `by` (= the xmit), both mispredicting, with an
even-older branch holding the secret load speculative.

LEAK SIGNATURE (commit_impl.hh:936 + iew_impl.hh:487): when bo and by collide, IEW keeps the
OLDEST mispredict (bo) as instCausingSquash; STT makes the whole squash PENDING iff that inst
isArgsTainted. So a TAINTED bo drags the YOUNGER UNTAINTED `by` into the pending squash — `by`'s
observable redirect is delayed purely because bo is (secret-) tainted.

Detected differentially against the untainted-bo twin (testsets/STT_6_pendsquash_ut):
    LEAK  ==  by is "made pending" in the TAINTED run  AND  not in the UNTAINTED run.

Timing: the even-older keep-speculative branch gets a large resolve_stall (resolve late, so the
load stays speculative → bo tainted); bo and by get 0 (resolve/collide early).

Usage: python3 pendsquash_diff.py [N] [keepspec_stall]
"""
import os, sys, json, tempfile, subprocess, re
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


def run_gadget(variant, stem, keepspec_stall, cut, bo_pc, by_pc):
    """Run the gadget; return (set of absolute PCs 'made pending', by_pending, bo_pending).
    `cut`, bo_pc, by_pc come from the TAINTED ann so both twins get IDENTICAL stalls."""
    ann = json.load(open(ROOT / f"testsets/{variant}/mispredict_not_taken/ann/{stem}.ann.json"))
    # keep-speculative branches (older than bo) resolve late; bo & by resolve early (collide)
    for a in ann["annotations"]:
        a["resolve_stall_cycles"] = keepspec_stall if a["branch_pc"] < cut else 0
    wd = Path(tempfile.mkdtemp(prefix="pendsq_"))
    ap = wd / f"{stem}.ann.json"
    ap.write_text(json.dumps(ann))
    binary = g.build_binary(ROOT / f"testsets/{variant}/mispredict_not_taken/asm/{stem}.s", wd)
    # nm label ranges: the jcc of pc{N} lies in [label(pcN), next label). Robust to the
    # exact movq/testq prefix length (br_bez vs br_cond) and to resolve_pc quirks.
    nm = subprocess.run(["nm", str(binary)], capture_output=True, text=True).stdout
    safe = stem.replace("-", "_")   # C symbols replace '-' with '_'
    labs = sorted((int(m.group(1), 16), int(m.group(2)))
                  for m in re.finditer(rf'([0-9a-f]+)\s+\w+\s+__litmus_{safe}_pc(\d+)\b', nm))
    addr_by_pc = {n: a for a, n in labs}
    nexts = {labs[i][1]: (labs[i + 1][0] if i + 1 < len(labs) else labs[i][0] + 64)
             for i in range(len(labs))}

    def pc_in_range(abs_pc, litmus_pc):
        lo = addr_by_pc.get(litmus_pc)
        return lo is not None and lo <= abs_pc < nexts[litmus_pc]

    trace = g.run_gem5(binary, wd, ann_path=ap)
    txt = Path(trace).read_text(errors="ignore")
    pend = set()
    for l in txt.splitlines():
        if "made pending" in l:
            m = re.search(r'PC \((0x[0-9a-f]+)', l)
            if m:
                pend.add(int(m.group(1), 16))
    by_pending = any(pc_in_range(p, by_pc) for p in pend)
    bo_pending = bo_pc is not None and any(pc_in_range(p, bo_pc) for p in pend)
    return pend, by_pending, bo_pending


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    ks = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    stems = sorted(p.stem for p in (ROOT / "testsets/STT_6_pendsquash/mispredict_not_taken/asm").glob("inst-*.s"))[:n]
    print(f"# pending-squash differential on /work/stt scheme2; {len(stems)} gadgets; keepspec_stall={ks}")
    print(f"# LEAK = by made pending iff bo tainted  (by is the YOUNGER UNTAINTED branch)\n")
    leaks = usable = 0
    for stem in stems:
        try:
            ann = json.load(open(ROOT / f"testsets/STT_6_pendsquash/mispredict_not_taken/ann/{stem}.ann.json"))
            bo = [a["branch_pc"] for a in ann["annotations"] if a.get("pendsquash_tainted")]
            bo_pc = bo[0] if bo else None
            by_pc = ann["xmit"]["pc"]
            cut = bo_pc if bo_pc is not None else by_pc
            _, by_pend_t, bo_pend_t = run_gadget("STT_6_pendsquash", stem, ks, cut, bo_pc, by_pc)
            _, by_pend_u, _         = run_gadget("STT_6_pendsquash_ut", stem, ks, cut, bo_pc, by_pc)
        except Exception as e:
            print(f"{stem}: ERROR {type(e).__name__}: {str(e)[:70]}")
            continue
        usable += 1
        leak = by_pend_t and not by_pend_u
        if leak:
            leaks += 1
        print(f"{stem}: bo=pc{bo_pc} by=pc{by_pc} | by_made_pending tainted={int(by_pend_t)} "
              f"untainted={int(by_pend_u)}  (bo_pending_t={int(bo_pend_t)}) {'<<< LEAK' if leak else ''}")
    print(f"\n# {leaks}/{usable} gadgets LEAK: the younger UNTAINTED branch's squash is delayed "
          f"iff the older branch is tainted (secret-dependent squash signal)")


if __name__ == "__main__":
    main()
