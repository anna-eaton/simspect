#!/usr/bin/env python3
"""Check whether each interleaved variant has a 2-load ALU feeding the xmit
load address (the OTB getOldestTaint merge structure). Structural sanity, not gem5."""
import re, glob, json, sys, os

def recs_of(path):
    recs = {}
    for line in open(path):
        m = re.search(r'_(pc\d+):.*?\\0A([a-z][^"]*?)", "([^"]*)"', line)
        if not m:
            continue
        pc, tmpl, cons = m.group(1), m.group(2), m.group(3)
        regs = re.findall(r'(?<!~)\{(\w+)\}', cons)   # exclude ~{memory} clobbers
        outs = re.findall(r'=&?\{(\w+)\}', cons)
        out = outs[0] if outs else None
        ins = regs[len(outs):]
        is_load = bool(re.search(r'movq\s+\d*\(', tmpl))
        is_alu = (not is_load) and bool(re.search(r'\b(leaq|addq|notq|xorq|orq|andq|subq)\b', tmpl))
        recs[pc] = dict(tmpl=tmpl, out=out, ins=ins, is_load=is_load, is_alu=is_alu)
    return recs

def merge_present(path):
    recs = recs_of(path)
    ann = json.load(open(path.replace('.ll', '.ann.json')))
    xpc = 'pc%d' % ann['xmit']['pc']
    if xpc not in recs:
        return None
    xins = recs[xpc]['ins']
    if not xins:
        return False
    addr_reg = xins[-1]            # index reg of the xmit load address
    loads = {r['out'] for r in recs.values() if r['is_load'] and r['out']}
    # ALU writing the address reg
    for r in recs.values():
        if r['out'] == addr_reg and r['is_alu']:
            load_ins = [x for x in r['ins'] if x in loads]
            return len(set(load_ins)) >= 2 or (len(r['ins']) >= 2 and len(set(load_ins)) >= 1)
    return False

d = sys.argv[1]
files = sorted(glob.glob(os.path.join(d, 'inst-*_v*.ll')))
tot = merged = none = 0
for f in files:
    r = merge_present(f)
    if r is None:
        none += 1; continue
    tot += 1; merged += 1 if r else 0
print(f"{merged}/{tot} variants have a 2-load ALU feeding xmit address  ({none} unparseable)")
