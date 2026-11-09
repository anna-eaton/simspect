#!/usr/bin/env python3
"""stage2_check.py — does Stage 2 (parsexml passes 1-5 + compile_annotate) scale to larger Alloy bounds?

stage15-bound session, 2026-11-08. Read-only use of the repo's STAGE2_compilation (copied into the
workspace unchanged). For each <ws>/xmlgen/<name>/xml/ it runs batch_generate.py (both branch modes),
once plain and once with fanout v2 (specs/fanout/stt.json's 'fanout_v2' + 'reg_naming'), then
compile_annotate.py on every .ll, and reports per variant: XML count, instruction count, Reg_s / Mem_s
atoms per instance (= pass-3 locked registers / memory slots), unresolved branches (= branch-annotation
hook entries), .ll produced, .s+.ann produced, and the first errors.

Usage: python3 stage2_check.py --ws /tests/stage15_bound_20261108 [--jobs 8]
Output: <ws>/stage2/<name>__<variant>/{<mode>/llvm, asm, ann}, <ws>/stage2/summary.json, log on stdout.
"""
import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def xml_stats(xml):
    t = xml.read_text()
    ins = set(re.findall(r'label="Instruction\$(\d+)"', t))
    regs = set(re.findall(r'label="Reg_s\$(\d+)"', t))
    mems = set(re.findall(r'label="Mem_s\$(\d+)"', t))
    # unresolved = instructions without an isresolved tuple
    m = re.search(r'<field label="isresolved"[^>]*>(.*?)</field>', t, re.S)
    res = set(re.findall(r'<atom label="Instruction\$(\d+)"/>', m.group(1))) if m else set()
    km = re.search(r'<field label="kind"[^>]*>(.*?)</field>', t, re.S)
    br = set()
    if km:
        for i, k in re.findall(r'<tuple> <atom label="Instruction\$(\d+)"/> <atom label="(T\w+)\$0"/> </tuple>', km.group(1)):
            if k.startswith("TBranch"):
                br.add(i)
    return len(ins), len(regs), len(mems), len(br - res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws", required=True)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    ws = Path(a.ws)
    s2 = ws / "STAGE2_compilation"
    fan = json.loads((ws / "specs/fanout/stt.json").read_text())
    variants = {"plain": [], "fanout_v2": ["--fanout-v2-config", json.dumps(fan["fanout_v2"]),
                                           "--reg-naming-config", json.dumps(fan["reg_naming"])]}
    summary = {}
    for xd in sorted((ws / "xmlgen").glob("*/xml")):
        name = xd.parent.name
        xmls = sorted(xd.glob("inst-*.xml"))
        if not xmls:
            continue
        st = [xml_stats(x) for x in xmls]
        base = {"xml": len(xmls), "instructions": sorted({s[0] for s in st}),
                "reg_s_max": max(s[1] for s in st), "mem_s_max": max(s[2] for s in st),
                "unresolved_br_max": max(s[3] for s in st),
                "reg_s_hist": {k: sum(1 for s in st if s[1] == k) for k in sorted({s[1] for s in st})}}
        for vname, extra in variants.items():
            out = ws / "stage2" / f"{name}__{vname}"
            cmd = [sys.executable, str(s2 / "batch_generate.py"), str(xd), "--out", str(out),
                   "--mode", "mispredict_not_taken", "--mode", "mispredict_taken"] + extra
            r = subprocess.run(cmd, capture_output=True, text=True)
            rec = dict(base, batch_rc=r.returncode, batch_tail=(r.stdout + r.stderr)[-600:])
            for mode in ("mispredict_not_taken", "mispredict_taken"):
                lls = sorted((out / mode).glob("*.ll")) if (out / mode).exists() else []
                asm, ann = out / mode / "asm", out / mode / "ann"
                asm.mkdir(parents=True, exist_ok=True)
                ann.mkdir(parents=True, exist_ok=True)

                def one(ll):
                    p = subprocess.run([sys.executable, str(s2 / "compile_annotate.py"), str(ll),
                                        "--out-dir", str(asm), "--ann-dir", str(ann)], capture_output=True, text=True)
                    return ll.name, p.returncode, (p.stderr or p.stdout).strip()[-300:]
                with ThreadPoolExecutor(a.jobs) as ex:
                    res = list(ex.map(one, lls))
                errs = [x for x in res if x[1] != 0]
                rec[mode] = {"ll": len(lls), "asm_ok": len(lls) - len(errs), "asm_err": len(errs),
                             "first_errors": errs[:3]}
            summary[f"{name}__{vname}"] = rec
            print(json.dumps({f"{name}__{vname}": {k: v for k, v in rec.items() if k != "batch_tail"}}), flush=True)
    (ws / "stage2").mkdir(exist_ok=True)
    (ws / "stage2/summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
