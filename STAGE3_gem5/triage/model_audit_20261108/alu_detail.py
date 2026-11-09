# Usage: python3 alu_detail.py <dir-with-inst-*.txt>   (needs shapes.py beside it). Splits ld->ALU->xm instances by whether the load reads memory (inmem+ddi) and the ALU has its ddi edge. MODEL_AUDIT_SPT_RECON.md Q2.
import sys, glob, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapes import parse, base
C = collections.Counter()
for f in sorted(glob.glob(os.path.join(sys.argv[1], 'inst-*.txt'))):
    R = parse(f)
    kind = {i: base(k) for i, k in R.get('Instruction<:kind', [])}
    owner = {}; slots = collections.defaultdict(lambda: collections.defaultdict(list))
    for s in ['inreg', 'inaddr', 'inmem', 'outreg', 'outmem']:
        for i, o in R.get(f'Instruction<:{s}', []): owner[o] = (i, s); slots[i][s].append(o)
    rf = R.get('Operand<:rf', []); ddi = set(R.get('Operand<:ddi', []))
    xm = [i for i, _ in R.get('Instruction<:isxm', [])][0]
    lop = slots[xm]['inaddr'] if kind[xm] in ('TLoad', 'TStore') else slots[xm]['inreg']
    for a, b in rf:
        if b in lop and kind[owner[a][0]] in ('TOthern', 'TOtherx'):
            o = owner[a][0]
            for a2, b2 in rf:
                if b2 in slots[o]['inreg'] and kind[owner[a2][0]] == 'TLoad':
                    l = owner[a2][0]
                    real_load = bool(slots[l]['inmem']) and any((m, a2) in ddi for m in slots[l]['inmem'])
                    alu_ddi = (b2, a) in ddi
                    C[('load_reads_mem_with_ddi', real_load, 'alu_ddi', alu_ddi)] += 1
print(dict(C))
