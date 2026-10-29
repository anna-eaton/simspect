import sys,json,re,subprocess
sys.path.insert(0,"/tests/simspect/STAGE3_gem5"); import gem5_common as gc
from pathlib import Path
s=Path(sys.argv[1]); name=s.stem
wd=Path(name+"_syms"); wd.mkdir(exist_ok=True)
b=gc.build_binary(s,wd)
syms={m.group(2):int(m.group(1),16) for L in subprocess.check_output(["objdump","-d",str(b)]).decode().splitlines() if (m:=re.match(r"\s*([0-9a-f]+)\s+<([^>]+)>:",L))}
br=syms[name+"_branch"]
ann={"branch_mode":"mispredict_not_taken","annotations":[{"branch_pc":0,"mode":"mispredict_not_taken","branch_addr":br,"branch_addr_hex":hex(br),"resolve_stall_cycles":2000}],"xmit":{"pc":1,"kind":"ld","addr":syms[name+"_xmit"]},"commit_boundary":{"first_noncommitted":{"pc":0,"addr":br}},"func_base_addr":0x401011}
Path(name+".ann.json").write_text(json.dumps(ann)); print(hex(br))
