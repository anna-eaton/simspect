import sys
sys.argv=['x']
exec(open(sys.path[0]+'/combos.py').read().split("for cn,xs in corp.items():")[0])
def valids(inst,tab):
    out=[]
    for k,spec in inst:
        c=CAT.get(k,'other_n'); cands=tab[c]
        out.append(len([n for n in cands if spec<=U[n]] or cands))
    return out
for cn,xs in corp.items():
    rs=recs(xs)
    print('==',cn,len(rs))
    for tn in ['today_superset','STT','SPT','InvisiSpec','DoM_Delay','STL']:
        tab=T[tn]; K=[max(valids(i,tab)) for i in rs]; O=[1+sum(v-1 for v in valids(i,tab)) for i in rs]
        print(f"  {tn:15s} cover-each K: {summ(K)} | OFAT: {summ(O)}")
