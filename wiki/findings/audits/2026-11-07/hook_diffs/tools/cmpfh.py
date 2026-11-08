import sys
def load(p):
    d={}
    for l in open(p):
        h,n,name=l.rstrip('\n').split(' ',2)
        d.setdefault(name,[]).append((h,int(n)))
    return d
a,b=load(sys.argv[1]),load(sys.argv[2])
same=diff=0
for k in sorted(set(a)|set(b)):
    if k not in a: print('ONLY_B',k); continue
    if k not in b: print('ONLY_A',k); continue
    if sorted(a[k])==sorted(b[k]): same+=1
    else: diff+=1; print('DIFF',a[k],b[k],k)
print('same',same,'diff',diff)
