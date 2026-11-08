import sys,re
# usage: pg.py file.txt regex [context]
f,pat=sys.argv[1],sys.argv[2]; ctx=int(sys.argv[3]) if len(sys.argv)>3 else 1
pages=open(f,encoding='utf-8',errors='replace').read().split('\f')
r=re.compile(pat,re.I)
for i,p in enumerate(pages,1):
    L=p.split('\n')
    for j,l in enumerate(L):
        if r.search(l):
            lo,hi=max(0,j-ctx),min(len(L),j+ctx+1)
            print(f"--- p{i} L{j}")
            print('\n'.join(x.strip() for x in L[lo:hi]))
