#!/usr/bin/env python3
"""Channel-D (IMPLICIT-FLOW) probe — does STT leak a secret through a PUBLIC load gated by a secret branch?

Gadget (inst-cd-001, derived from base STT_6 inst-000012):
    pc1: movq (-8(%rsp)), %rax        # secret load (tainted)
    pc5: movq %rax,%rcx; testq; je    # SECRET-dependent branch (transmitter is NOT this branch)
    pc6: leaq -16(%rsp),%r11; movq (%r11),%r11   # PUBLIC load, CONSTANT (untainted) address, gated by pc5
The transmitter is the pc6 load. Its ADDRESS is untainted, so STT's data-flow tracker does not protect it.
The question: does the pc6 load's CACHE ACCESS depend on the secret (an implicit/control-dependence leak)?

Method = the same non-interference frame as check_br_ni: VALUE-FLIP the in-memory secret (0 vs 1) on one
binary; the observable is the pc6 load's first cache-touch tick (LSQ execute_tick / packet_tick). Run under
scheme 0 (Unsafe, positive control) and scheme 2 (STT).

  leak  = pc6 access tick MOVES with the secret under scheme 2
  sound = pc6 access invariant under scheme 2
  (control: if it's invariant even under scheme 0, the gadget forms NO single-level implicit channel —
   the speculative path is predictor-determined, so pc6 executes speculatively at a secret-independent
   tick regardless; that is the expected result and the soundness argument in CHANNEL_D_DESIGN.md.)

Usage: python3 channel_d/channel_d_probe.py [stall]
"""
import os, sys, json, tempfile, subprocess, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.update(
    SIMSPECT_GEM5_BIN="/work/stt/build/X86/gem5.opt", SIMSPECT_GEM5_DIR="/work/stt",
    SIMSPECT_SE_CONFIG="/work/stt/configs/example/se.py", SIMSPECT_GEM5_CPU="DerivO3CPU",
    SIMSPECT_GEM5_DBG_FLAG="O3PipeView,LSQUnit,Commit", SIMSPECT_BRANCH_ANN_ENABLE="1",
    SIMSPECT_GEM5_TIMEOUT_S="120")
sys.path.insert(0, str(ROOT / "STAGE3_gem5"))
import gem5_common as g

HERE = Path(__file__).resolve().parent
STEM = "inst-cd-001"


def _secret_value_asm(s_path, secret, wd):
    if secret == 0:
        return s_path
    out = wd / s_path.name
    out.write_text(re.sub(r'(movq\s+)\$0(,\s*-?\d+\(%rsp\))', rf'\g<1>${secret}\g<2>', s_path.read_text()))
    return out


def pc6_access(stall, secret, scheme):
    """Return (execute_tick, packet_tick) of the pc6 public load, or (None,None)."""
    g._scheme = scheme
    ann = json.load(open(HERE / f"{STEM}.ann.json"))
    cut = 5                                          # window-opening branches are pc<5 (the secret branch)
    for a in ann["annotations"]:
        a["resolve_stall_cycles"] = stall if a["branch_pc"] < cut else 0
    wd = Path(tempfile.mkdtemp(prefix="cd_"))
    ap = wd / f"{STEM}.ann.json"; ap.write_text(json.dumps(ann))
    binary = g.build_binary(_secret_value_asm(HERE / f"{STEM}.s", secret, wd), wd)
    nm = subprocess.run(["nm", str(binary)], capture_output=True, text=True).stdout
    m = re.search(rf'([0-9a-f]+)\s+\w+\s+__litmus_{STEM.replace("-","_")}_pc6\b', nm)
    pc6_addr = int(m.group(1), 16)
    trace = g.run_gem5(binary, wd, ann_path=ap)
    lsq = g.parse_lsq(trace)
    # the pc6 label is on the leaq; the actual LOAD (movq (%r11),%r11) is a few bytes later — scan range
    recs = [r for pc, rs in lsq.items() if pc6_addr <= pc < pc6_addr + 16 for r in rs]
    if not recs:
        return None, None
    r = min(recs, key=lambda d: d.get("execute_tick") or 1 << 62)
    return r.get("execute_tick"), r.get("packet_tick")


def main():
    stall = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    print(f"# Channel-D implicit-flow probe — pc6 PUBLIC load gated by secret branch | /work/stt | stall={stall}")
    print(f"# observable = pc6 load first cache-touch tick (execute_tick, packet_tick); VALUE-FLIP secret 0 vs 1\n")
    for scheme, label in [(0, "scheme0 (Unsafe, control)"), (2, "scheme2 (STT)")]:
        a = pc6_access(stall, 0, scheme)
        b = pc6_access(stall, 1, scheme)
        moves = (a != b)
        print(f"{label}: secret0 pc6=(exec={a[0]},pkt={a[1]})  secret1 pc6=(exec={b[0]},pkt={b[1]})  "
              f"-> {'MOVES (channel)' if moves else 'INVARIANT'}")
    print("\n# Interpretation: if scheme0 is already INVARIANT, no single-level implicit channel exists")
    print("#   (speculative path is predictor-determined). A scheme2 MOVE with a scheme0 MOVE = real leak.")


if __name__ == "__main__":
    main()
