import json,re,glob,os,sys
def load(p):
    s=open(p).read()
    out=[];i=0;n=len(s);ins=False
    while i<n:
        c=s[i]
        if ins:
            out.append(c)
            if c=='\\': out.append(s[i+1]); i+=2; continue
            if c=='"': ins=False
            i+=1; continue
        if c=='"': ins=True; out.append(c); i+=1; continue
        if s.startswith('//',i):
            j=s.find('\n',i); i=n if j<0 else j; continue
        if s.startswith('/*',i):
            j=s.find('*/',i); i=n if j<0 else j+2; continue
        out.append(c); i+=1
    t=''.join(out)
    t=re.sub(r',(\s*[}\]])',r'\1',t)
    return json.loads(t)
pats=sys.argv[1:]
for pat in pats:
  for p in sorted(glob.glob(pat)):
    try: c=load(p)
    except Exception as e: print("ERR",p,e); continue
    g=c.get('gem5',{}); sw=c.get('sweep',{})
    mt=os.path.getmtime(p)
    import time
    print(time.strftime('%Y-%m-%d',time.localtime(mt)),'|',p,'|',g.get('binary'),'|',os.path.basename(str(g.get('config_script'))),'|s',g.get('scheme'),'|',' '.join(g.get('extra_args') or []),'|ann',g.get('branch_ann_enable'),'|fnc',g.get('fnc_commit_stall_cycles'),'|stl',g.get('stl_ann_enable'),g.get('stl_alias_pred'),g.get('stl_store_stall_cycles'),'|chk',g.get('checker'),'|caches',g.get('caches'),'|unres',sw.get('unresolved_stall_cycles'))
