#!/usr/bin/env python3
"""Empirical InvisiSpec KV1 demo (speculative L1I instruction-fetch footprint).

A branch (rdx=0 -> actually NOT taken) whose BTB prediction is forced TAKEN to a far
code label `kv1_far` reached ONLY speculatively (the correct path falls through to
`jmp kv1_end`, skipping it). Under InvisiSpec the spec data path is invisible, but
instruction fetches are NOT -> the wrong-path fetch of kv1_far installs its L1I line.
  mispredict_taken : kv1_far's I-line installs (Ifetch NP>IS) speculatively = KV1
  correctly_not_taken (control): kv1_far never fetched -> NO install
Build: /work/amulet/amulet-gem5-InvisiSpec_AE-v1.1 (Ruby, SpectreSafeInvisibleSpec).
Gate: STRICT lc/fnc (resolve-stall + fnc-stall hooks).
"""
import json, subprocess, re, sys
from pathlib import Path
sys.path.insert(0, "/tests/simspect/STAGE3_gem5")
import gem5_common as gc
B="/work/amulet/amulet-gem5-InvisiSpec_AE-v1.1"; GEM5=f"{B}/build/X86_MESI_Two_Level/gem5.opt"; SE=f"{B}/configs/example/se.py"
HERE=Path(__file__).resolve().parent
wd=HERE/"kv1gadget_wd"; wd.mkdir(exist_ok=True)
b=gc.build_binary(HERE/"kv1gadget.s", wd)
syms={m.group(2):int(m.group(1),16) for L in subprocess.check_output(["objdump","-d",str(b)]).decode().splitlines() if (m:=re.match(r'\s*([0-9a-f]+)\s+<([^>]+)>:',L))}
BR=syms["kv1_branch"]; FAR=syms["kv1_far"]
def run(tag, mode):
    ann={"branch_mode":mode,"annotations":[{"branch_pc":0,"mode":mode,"branch_addr":BR,"branch_addr_hex":hex(BR),
        "btb_forced_target_addr":FAR,"btb_forced_target_addr_hex":hex(FAR),"resolve_stall_cycles":2000}],
        "xmit":{"pc":1,"kind":"br_x","addr":BR,"addr_hex":hex(BR)},
        "commit_boundary":{"first_noncommitted":{"pc":0,"addr":BR,"addr_hex":hex(BR)}},
        "func_base_addr":syms["kv1gadget"],"func_base_addr_hex":hex(syms["kv1gadget"])}
    ap=HERE/f"{tag}.ann.json"; ap.write_text(json.dumps(ann,indent=1))
    od=HERE/f"{tag}_out"; od.mkdir(exist_ok=True)
    subprocess.run([GEM5,f"--outdir={od}","--debug-flags=ProtocolTrace,TLB","--debug-file=t.out",SE,f"--cmd={b}",
        "--cpu-type=DerivO3CPU","--caches","--scheme=SpectreSafeInvisibleSpec","--ruby","--needsTSO=1","--allowSpecBuffHit=1",
        f"--branch-ann-file={ap}",f"--branch-ann-base={hex(syms['kv1gadget'])}",f"--fnc-commit-stall-pc={hex(BR)}","--fnc-commit-stall-cycles=150"],
        capture_output=True,timeout=240)
    txt=(od/"t.out").read_text(errors="replace")
    pad=re.search(rf"itb: Translated 0x{FAR:x} -> (0x[0-9a-f]+)",txt)
    farpad=int(pad.group(1),16)&~0x3f if pad else None
    installs={l for _,l in re.findall(r"L1Cache\s+Ifetch\s+NP>IS\s+\[(0x[0-9a-f]+), line (0x[0-9a-f]+)\]",txt)}
    hit = (farpad is not None) and (hex(farpad) in installs)
    return farpad, hit
fp1,h1=run("kv1mispred","mispredict_taken")
fp0,h0=run("kv1control","correctly_not_taken")
print(f"kv1_far(0x{FAR:x}) L1I install: mispredict_taken={h1} (paddr {fp1 and hex(fp1)}) | control={h0}")
print("KV1 = kv1_far's L1I line installs ONLY under the misprediction (speculative wrong-path fetch, unprotected).")
