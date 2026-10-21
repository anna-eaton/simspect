#!/usr/bin/env python3
"""Empirical STT KV3 demo (spec store → unprotected TLB fill).

Builds two gadgets identical except the speculative transmitter (store vs load):
a mispredicted branch (held unresolved via resolve_stall) guards a spec load of a
tainted index -> the xmit accesses kv_buf + index*4096 (a COLD page). Runs each on
the STT build under --scheme=2 (STT) and --scheme=0 (Unsafe) and reports whether the
cold page gets a TLB walk+fill.

Expected (KV3): store walks under BOTH STT and Unsafe (STT doesn't protect stores);
load walks under Unsafe but NOT under STT (STT defers the spec load). store STT-walk
== the bug.  Build: /work/stt. Gate: STRICT lc/fnc (resolve_stall + fnc-stall hooks).
"""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, "/tests/simspect/STAGE3_gem5")
import gem5_common as gc
STT="/work/stt"; GEM5=f"{STT}/build/X86/gem5.opt"; SE=f"{STT}/configs/example/se.py"
HERE=Path(__file__).resolve().parent
def build_and_pcs(name):
    wd=HERE/f"{name}_wd"; wd.mkdir(exist_ok=True)
    b=gc.build_binary(HERE/f"{name}.s", wd)
    import re
    syms={m.group(2):int(m.group(1),16) for L in subprocess.check_output(["objdump","-d",str(b)]).decode().splitlines()
          if (m:=re.match(r'\s*([0-9a-f]+)\s+<([^>]+)>:',L))}
    kb=next(int(L.split()[0],16) for L in subprocess.check_output(["objdump","-t",str(b)]).decode().splitlines() if " kv_buf" in L)
    return b, syms[f"{name}_branch"], syms[f"{name}_xmit"], kb+8*4096
def run(name, b, br, scheme):
    ann={"branch_mode":"mispredict_not_taken","annotations":[{"branch_pc":0,"mode":"mispredict_not_taken",
        "branch_addr":br,"branch_addr_hex":hex(br),"resolve_stall_cycles":2000}],
        "xmit":{"pc":2,"kind":"ld","addr":br,"addr_hex":hex(br)},
        "commit_boundary":{"first_noncommitted":{"pc":0,"addr":br,"addr_hex":hex(br)}},
        "func_base_addr":0x401011,"func_base_addr_hex":"0x401011"}
    ap=HERE/f"{name}.ann.json"; ap.write_text(json.dumps(ann,indent=1))
    od=HERE/f"{name}_s{scheme}"; od.mkdir(exist_ok=True)
    subprocess.run([GEM5,f"--outdir={od}","--debug-flags=TLB","--debug-file=t.out",SE,f"--cmd={b}",
        "--cpu-type=DerivO3CPU","--caches",f"--scheme={scheme}",f"--branch-ann-file={ap}",
        f"--branch-ann-base=0x401011",f"--fnc-commit-stall-pc={hex(br)}","--fnc-commit-stall-cycles=150"],
        capture_output=True,timeout=240)
    return (od/"t.out").read_text(errors="replace").count("Handling a TLB miss for address 0x40b000")
print(f"{'gadget':9} {'STT(s2)':9} {'Unsafe(s0)':10}")
for name in ("kv3store","kv3load"):
    b,br,xmit,cold=build_and_pcs(name)
    print(f"{name:9} walk={run(name,b,br,2):<6} walk={run(name,b,br,0)}")
print("KV3 = kv3store walks under STT(s2); kv3load does NOT (protected) but walks under Unsafe(s0).")
