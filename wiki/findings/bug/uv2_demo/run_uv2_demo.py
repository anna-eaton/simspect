#!/usr/bin/env python3
"""Empirical InvisiSpec UV2 demo (single-thread MSHR/TBE contention).

4 speculative loads to 4 distinct COLD lines on a TLB-WARM page (a committed load to a
far line on the same page first — otherwise InvisiSpec defers the speculative TLB miss and
the load never issues its GETSPEC; that was the long-standing blocker). Under a mispredicted
branch held unresolved (resolve_stall=3000) all 4 issue invisible spec reads (SpecLoad NP>IX,
each allocating a TBE). Control = --L1_TBEs:
  TBEs=8 -> 4 GETSPECs, all concurrent (~1.5k-tick spread), no contention.
  TBEs=2 -> pool exhausted: the 3rd/4th loads retry-storm (~250 NP>IX) and are delayed ~120k
            ticks waiting for a TBE = the single-thread MSHR/TBE interference channel (UV2).
Source: L1cache.sm:1189 stalls a request to a line in IX; 2-entry TBE pool (Ruby.py L1_TBEs=2).
Build: /work/amulet/amulet-gem5-InvisiSpec_AE-v1.1 (Ruby, SpectreSafeInvisibleSpec). STRICT lc/fnc.
NOTE: --L1_TBEs is AMuLeT's own default (2); 8 is the no-contention control (a cache-param knob).
"""
import sys, subprocess, re, json
from pathlib import Path
sys.path.insert(0,"/tests/simspect/STAGE3_gem5"); import gem5_common as gc
B="/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1"; GEM5=f"{B}/build/X86_MESI_Two_Level/gem5.opt"; SE=f"{B}/configs/example/se.py"
HERE=Path(__file__).resolve().parent
wd=HERE/"wd"; wd.mkdir(exist_ok=True)
b=gc.build_binary(HERE/"uv2x.s",wd)
syms={m.group(2):int(m.group(1),16) for L in subprocess.check_output(["objdump","-d",str(b)]).decode().splitlines() if (m:=re.match(r'\s*([0-9a-f]+)\s+<([^>]+)>:',L))}
BR=syms["uv2x_branch"]; FUNC=syms["uv2x"]
def run(tbes):
    ann={"branch_mode":"mispredict_not_taken","annotations":[{"branch_pc":0,"mode":"mispredict_not_taken",
        "branch_addr":BR,"branch_addr_hex":hex(BR),"resolve_stall_cycles":3000}],
        "xmit":{"pc":1,"kind":"ld","addr":BR,"addr_hex":hex(BR)},
        "commit_boundary":{"first_noncommitted":{"pc":0,"addr":BR,"addr_hex":hex(BR)}},
        "func_base_addr":FUNC,"func_base_addr_hex":hex(FUNC)}
    ap=HERE/f"a{tbes}.json"; ap.write_text(json.dumps(ann,indent=1))
    od=HERE/f"out{tbes}"; od.mkdir(exist_ok=True)
    subprocess.run([GEM5,f"--outdir={od}","--debug-flags=ProtocolTrace","--debug-file=t.out",SE,f"--cmd={b}",
        "--cpu-type=DerivO3CPU","--caches","--scheme=SpectreSafeInvisibleSpec","--ruby","--needsTSO=1","--allowSpecBuffHit=1",
        f"--L1_TBEs={tbes}",f"--branch-ann-file={ap}","--branch-ann-base="+hex(FUNC),f"--fnc-commit-stall-pc={hex(BR)}","--fnc-commit-stall-cycles=250"],
        capture_output=True,timeout=240)
    txt=(od/"t.out").read_text(errors="replace")
    ticks=[int(m.group(1)) for L in txt.splitlines() if (m:=re.search(r"^\s*(\d+)\s.*SpecLoad\s+NP>IX",L))]
    spread=(max(ticks)-min(ticks)) if len(ticks)>1 else 0
    return len(ticks), spread
for tb in (8,2):
    n,s=run(tb); print(f"L1_TBEs={tb}: GETSPEC(NP>IX) events={n:<4} issue-tick spread={s}")
print("UV2 = TBEs=2 retry-storms + serializes the 4 spec loads (pool exhausted); TBEs=8 issues all concurrently.")
