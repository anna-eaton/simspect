#!/usr/bin/env python3
# Usage: python3 stale.py <dir-with-inst-*.txt>   (needs shapes.py beside it). Counts instances with a stale rf edge (reads a state past a newer same-state writer) and those feeding xm. MODEL_AUDIT_SPT_RECON.md R-3.
"""stale.py DIR -- per instance: stale rf (an rf edge reads a state past a newer same-state writer),
and whether such an edge feeds xm's leak operand (ld inaddr / br_x inreg / st inaddr)."""
import sys, glob, os, collections
sys.path.insert(0, os.path.dirname(__file__))
from shapes import parse, base
def order_of(R):
    ins=[a for (a,) in R.get('Instruction',[])]; spo=dict(R.get('Instruction<:spo',[]))
    first=[i for i in ins if i not in set(spo.values())]; o=[]; c=first[0] if first else None
    while c: o.append(c); c=spo.get(c)
    return {i:k for k,i in enumerate(o)}
C=collections.Counter(); n=0
for f in sorted(glob.glob(os.path.join(sys.argv[1],'**','inst-*.txt'),recursive=True)):
    R=parse(f); pos=order_of(R); n+=1
    owner={}
    for s in ['inreg','inaddr','inmem','outreg','outmem']:
        for i,o in R.get(f'Instruction<:{s}',[]): owner[o]=(i,s)
    st=dict(R.get('Operand<:opstate',[]))
    outs=[o for o,(i,s) in owner.items() if s in('outreg','outmem')]
    kind={i:base(k) for i,k in R.get('Instruction<:kind',[])}
    xm=[i for i,_ in R.get('Instruction<:isxm',[])]
    stale=False; stale_x=False
    for a,b in R.get('Operand<:rf',[]):
        pa=pos[owner[a][0]]; pb=pos[owner[b][0]]
        for w in outs:
            if w!=a and st.get(w)==st.get(a) and pa<pos[owner[w][0]]<pb:
                stale=True
                if xm and owner[b][0]==xm[0] and owner[b][1] in('inaddr','inreg'): stale_x=True
    C['stale_rf']+=stale; C['stale_rf_to_xm']+=stale_x
print(sys.argv[1], n, dict(C))
