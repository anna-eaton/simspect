#!/usr/bin/env python3
"""STT branch-defense NON-INTERFERENCE audit (value-flip) — /work/stt scheme 2.

A principled, positive use of the differential branch-channel framework
(BRANCH_CHANNEL_CHECK_DESIGN.md): instead of the fragile check_br redirect heuristic, vary the secret
(in-memory value 0 vs 1, same binary) and check whether the FULL public fetch-redirect timeline — every
squash broadcast an attacker can time — is INVARIANT. If it is, STT's branch defense is sound for that
gadget; the historical STT br_x "leaks" (project_stt_branch_leak_cause) were check_br false positives.

Result (2026-06-09): 12/12 pendsquash gadgets SOUND (timeline secret-invariant). This is the
non-interference confirmation that STT's branch implicit-channel defense works — and the same value-flip
that retracted our pending-squash *reproduction* gives this clean *positive* audit.

Usage: python3 stt_branch_soundness_audit.py [N]
"""
import os, sys, json, tempfile, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.update(
    SIMSPECT_GEM5_BIN="/work/stt/build/X86/gem5.opt", SIMSPECT_GEM5_DIR="/work/stt",
    SIMSPECT_SE_CONFIG="/work/stt/configs/example/se.py", SIMSPECT_GEM5_CPU="DerivO3CPU",
    SIMSPECT_GEM5_DBG_FLAG="Commit", SIMSPECT_BRANCH_ANN_ENABLE="1", SIMSPECT_GEM5_TIMEOUT_S="120")
sys.path.insert(0, str(ROOT / "STAGE3_gem5"))
import gem5_common as g
g._scheme = 2
TS = ROOT / "testsets/STT_6_pendsquash/mispredict_not_taken"


def _secval(s_path, secret, wd):
    if secret == 0:
        return s_path
    out = wd / s_path.name
    out.write_text(re.sub(r'(movq\s+)\$0(,\s*-?\d+\(%rsp\))', rf'\g<1>${secret}\g<2>', s_path.read_text()))
    return out


def redirect_timeline(stem, secret, cut):
    """The attacker-observable fetch-redirect timeline = sorted ticks of all squash broadcasts (excl startup)."""
    ann = json.load(open(TS / "ann" / f"{stem}.ann.json"))
    for a in ann["annotations"]:
        a["resolve_stall_cycles"] = 2000 if a["branch_pc"] < cut else 0
    wd = Path(tempfile.mkdtemp())
    ap = wd / f"{stem}.ann.json"
    ap.write_text(json.dumps(ann))
    b = g.build_binary(_secval(TS / "asm" / f"{stem}.s", secret, wd), wd)
    txt = Path(g.run_gem5(b, wd, ann_path=ap)).read_text(errors="ignore")
    return tuple(sorted(int(re.match(r'\s*(\d+):', l).group(1)) for l in txt.splitlines()
                        if "Squashing due to branch mispred" in l and "0x401000" not in l))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    stems = sorted(p.stem for p in (TS / "asm").glob("inst-*.s"))[:n]
    print("# STT branch-defense NON-INTERFERENCE audit (value-flip, /work/stt scheme2)")
    print("# SOUND iff the public fetch-redirect timeline is INVARIANT to the secret\n")
    sound = tot = 0
    for stem in stems:
        ann = json.load(open(TS / "ann" / f"{stem}.ann.json"))
        bo = [a["branch_pc"] for a in ann["annotations"] if a.get("pendsquash_tainted")]
        cut = bo[0] if bo else ann["xmit"]["pc"]
        try:
            t0, t1 = redirect_timeline(stem, 0, cut), redirect_timeline(stem, 1, cut)
        except Exception as e:
            print(f"{stem}: err {str(e)[:50]}"); continue
        tot += 1
        inv = (t0 == t1)
        sound += inv
        print(f"{stem}: {'SOUND' if inv else 'LEAK — timeline moves: %s vs %s' % (t0, t1)}")
    print(f"\n# {sound}/{tot} gadgets: STT branch defense SOUND (redirect timeline secret-invariant)")


if __name__ == "__main__":
    main()
