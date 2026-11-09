#!/usr/bin/env python3
# Usage: python3 shapes.py <dir-with-inst-*.txt> [spt|stt]   (spt adds store transmitters). Census of Alloy instance dumps: ALU on xm's leak-operand path, direct-load feed, declassify-same-value shape. Used for MODEL_AUDIT_SPT_RECON.md Q2.
"""shapes.py DIR [--leak spt|stt]  -- census of Alloy instance .txt dumps (model-audit 2026-11-08).
Per instance: is an ALU (Other*) op in the rf+ddi backward cone of xm's leak operand?
direct = xm leak operand rf-fed straight from a load outreg. declass (SPT) = the xm leak
operand's rf producer also rf-feeds a NON-speculative transmitter operand.
Uses rf (not shared opstate); program order from spo; atoms compared without $N."""
import re, sys, glob, os, json, collections
pat = re.compile(r'this/([A-Za-z_]+(?:<:[A-Za-z_]+)?)=\{(.*)\}')
def parse(path):
    R = {}
    for line in open(path):
        m = pat.match(line.strip())
        if not m: continue
        body = m.group(2).strip()
        R[m.group(1)] = [tuple(x.strip() for x in t.split('->')) for t in body.split(',')] if body else []
    return R
def base(a): return a.split('$')[0]
def analyze(path, leak):
    R = parse(path)
    ins = [a for (a,) in R.get('Instruction', [])]
    kind = {i: base(k) for i, k in R.get('Instruction<:kind', [])}
    spo = dict(R.get('Instruction<:spo', []))
    has_pred = set(spo.values())
    first = [i for i in ins if i not in has_pred]
    order = []
    cur = first[0] if first else None
    while cur:
        order.append(cur); cur = spo.get(cur)
    res = {i for i, _ in R.get('Instruction<:isresolved', [])}
    com = {i for i, _ in R.get('Instruction<:iscommitted', [])}
    xm = [i for i, _ in R.get('Instruction<:isxm', [])]
    slots = collections.defaultdict(lambda: collections.defaultdict(list))
    owner = {}
    for s in ['inreg', 'inaddr', 'inmem', 'outreg', 'outmem']:
        for i, o in R.get(f'Instruction<:{s}', []):
            slots[i][s].append(o); owner[o] = (i, s)
    rf = R.get('Operand<:rf', []); ddi = R.get('Operand<:ddi', [])
    back = collections.defaultdict(list)
    for a, b in rf + ddi: back[b].append(a)
    rf_src = {b: a for a, b in rf}
    # speculation contract: uncommitted and after an unresolved branch
    spec = set(); seen_unres = False
    for i in order:
        if seen_unres and i not in com: spec.add(i)
        if kind[i] in ('TBranchn', 'TBranchx') and i not in res: seen_unres = True
    def leakops(i):
        k = kind[i]
        if k == 'TLoad': return slots[i]['inaddr']
        if k == 'TBranchx': return slots[i]['inreg']
        if k == 'TStore' and leak == 'spt': return slots[i]['inaddr']
        return []
    out = {}
    if not xm: return None
    x = xm[0]
    out['xm_kind'] = kind[x]
    lops = leakops(x)
    # backward cone
    cone_ops = set(); stack = list(lops)
    while stack:
        o = stack.pop()
        for p in back[o]:
            if p not in cone_ops: cone_ops.add(p); stack.append(p)
    cone_instrs = {owner[o][0] for o in cone_ops if o in owner} - {x}
    out['alu_on_path'] = any(kind[i] in ('TOthern', 'TOtherx') for i in cone_instrs)
    def cone_of_instr(i):
        st = [o for s_ in ('inreg', 'inaddr', 'inmem') for o in slots[i][s_]]; seen = set()
        while st:
            o = st.pop()
            for p_ in back[o]:
                if p_ not in seen: seen.add(p_); st.append(p_)
        return {owner[o][0] for o in seen if o in owner}
    out['alu_on_load_path'] = any(kind[i] in ('TOthern', 'TOtherx') and any(kind[j] == 'TLoad' for j in cone_of_instr(i)) for i in cone_instrs)
    out['load_in_cone'] = any(kind[i] == 'TLoad' for i in cone_instrs)
    out['n_alu_total'] = sum(kind[i] in ('TOthern', 'TOtherx') for i in ins)
    prods = [rf_src.get(o) for o in lops]
    out['direct_load'] = any(p and owner[p][0] in kind and kind[owner[p][0]] == 'TLoad' and owner[p][1] == 'outreg' for p in prods)
    out['direct_alu'] = any(p and kind[owner[p][0]] in ('TOthern', 'TOtherx') for p in prods)
    out['unfed_leakop'] = any(p is None for p in prods)
    # declassification shape (SPT): producer also feeds a nonspec transmitter operand
    nonspec_x = set()
    for i in ins:
        if i in spec: continue
        for o in leakops(i):
            if i != x: nonspec_x.add(o)
    dec = False
    for p in prods:
        if p is None: continue
        for a, b in rf:
            if a == p and b in nonspec_x: dec = True
    out['declass_same_value'] = dec
    out['n_instr'] = len(ins)
    return out
def main():
    d = sys.argv[1]; leak = sys.argv[2] if len(sys.argv) > 2 else 'stt'
    files = sorted(glob.glob(os.path.join(d, '**', 'inst-*.txt'), recursive=True))
    C = collections.Counter(); ex = collections.defaultdict(list); n = 0
    for f in files:
        r = analyze(f, leak)
        if r is None: C['no_xm'] += 1; continue
        n += 1
        C['xm_' + r['xm_kind']] += 1
        if r['alu_on_load_path']: C['alu_on_load_path__' + r['xm_kind']] += 1
        for k in ('alu_on_path', 'alu_on_load_path', 'load_in_cone', 'direct_load', 'direct_alu', 'unfed_leakop', 'declass_same_value'):
            if r[k]:
                C[k] += 1
                if len(ex[k]) < 3: ex[k].append(os.path.relpath(f, d))
        if r['n_alu_total']: C['has_any_alu'] += 1
    print(json.dumps({'dir': d, 'n': n, 'counts': dict(C), 'examples': ex}, indent=1))
if __name__ == "__main__": main()
