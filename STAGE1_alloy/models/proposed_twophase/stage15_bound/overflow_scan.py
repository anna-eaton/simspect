#!/usr/bin/env python3
"""overflow_scan.py — count instances whose per-instruction operand counts break the skeleton's
cardinality facts (limited_inregs <=2, limited_inaddrs <=1, limited_inmems <=1, limited_ins <=2,
limited_outs <=1). With Alloy's default 4-bit Int (-8..7) and overflow allowed, '#(i.inaddr) <= 1'
is TRUE when the count is 8 (wraps to -8), so these facts stop binding once >= 8 operands can sit on
one instruction. stage15-bound 2026-11-08. Usage: overflow_scan.py <dir-with-inst-*.txt> [...]"""
import sys, glob, collections
sys.path.insert(0, __file__.rsplit('/', 5)[0])
import stage_seed
for d in sys.argv[1:]:
    files = sorted(glob.glob(f"{d}/inst-*.txt")); bad = 0; worst = 0
    for f in files:
        r = stage_seed.parse_txt(f); c = collections.Counter(); ins = collections.Counter()
        for s in ("inreg", "inaddr", "inmem", "outreg", "outmem"):
            for i, o in r.get(f"Instruction<:{s}", []):
                c[(i, s)] += 1
                if s in ("inreg", "inaddr", "inmem"): ins[i] += 1
        lim = {"inreg": 2, "inaddr": 1, "inmem": 1}
        viol = any(n > lim.get(s, 1) for (i, s), n in c.items() if s in lim) or any(n > 2 for n in ins.values()) \
            or any(c[(i, "outreg")] + c[(i, "outmem")] > 1 for i in {k[0] for k in c})
        worst = max([worst] + list(ins.values()))
        bad += viol
    print(f"{d.rstrip('/').split('/')[-1]}: {bad}/{len(files)} violate the cardinality facts; max ins on one instr = {worst}")
