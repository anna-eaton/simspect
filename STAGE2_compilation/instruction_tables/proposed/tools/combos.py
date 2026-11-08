import sys, glob, math, json, collections
R='/Users/annaeaton/Documents/stanford/trippel/simspect/'
sys.path.insert(0, R+'STAGE2_compilation'); sys.dont_write_bytecode=True
import parsexml as P
L3={'inaddr','inmem','outreg'}; S3={'inreg0','inaddr','outmem'}; A3={'inreg0','inreg1','outreg'}; A2={'inreg0','outreg'}
U={'load':L3,'load_zx8':L3,'load_zx16':L3,'load_32':L3,'load_sx32':L3,'load_disp':L3,'load_idx8':L3,'load_op_add':L3,'load_cmov':L3,
   'prefetch':{'inaddr','inmem'},'store':S3,'store8':S3,'store16':S3,'store32':S3,'store_imm':{'inaddr','outmem'},
   'bitnot':A2,'add':A3,'zsm':A3,'div':A3,'mov':A2,'addq':A3,'sub':A3,'xor':A3,'and':A3,'or':A3,'shl_imm':A2,'lea_scaled':A3,'mov_imm':{'outreg'},
   'br_c':{'inreg0'},'br_cmp':{'inreg0'}}
Lw=['load','load_zx8','load_zx16','load_32']
T={
 'current':        dict(ld=['load'],str=['store'],other_n=['bitnot','add'],other_x=['zsm','div'],br=['br_c']),
 'today_superset': dict(ld=['load'],str=['store'],other_n=['bitnot','add','zsm','div'],other_x=['zsm','div'],br=['br_c']),
 'today_taint':    dict(ld=['load'],str=['store'],other_n=['bitnot','add','zsm'],other_x=['zsm','div'],br=['br_c']),
 'STT':   dict(ld=Lw+['load_disp','load_idx8','load_op_add','load_cmov','prefetch'],str=['store','store8','store16','store32','store_imm'],
              other_n=['bitnot','add','zsm','mov','addq','xor','and','shl_imm','lea_scaled','mov_imm'],other_x=['zsm','div'],br=['br_c','br_cmp']),
 'ReCon': dict(ld=Lw+['load_disp','load_idx8','load_op_add','load_cmov','prefetch'],str=['store','store8','store16','store32','store_imm'],
              other_n=['bitnot','add','zsm','mov','addq','xor','and','shl_imm','lea_scaled','mov_imm'],other_x=['zsm','div'],br=['br_c','br_cmp']),
 'SPT':   dict(ld=Lw+['load_sx32','load_disp','load_op_add'],str=['store','store8','store16','store32','store_imm'],
              other_n=['bitnot','add','zsm','mov','addq','sub','xor','and','or','shl_imm','lea_scaled','mov_imm'],other_x=['zsm','div'],br=['br_c','br_cmp']),
 'InvisiSpec': dict(ld=Lw+['load_op_add','load_cmov','prefetch'],str=['store','store8','store16','store32'],
              other_n=['bitnot','add','zsm','div','mov','xor','shl_imm'],other_x=['zsm','div'],br=['br_c']),
 'CleanupSpec': dict(ld=Lw+['load_op_add','load_cmov','prefetch'],str=['store','store8','store16','store32'],
              other_n=['bitnot','add','zsm','div'],other_x=['zsm','div'],br=['br_c']),
 'SpecLFB': dict(ld=Lw+['load_op_add','load_cmov','prefetch'],str=['store'],
              other_n=['bitnot','add','zsm','div'],other_x=['zsm','div'],br=['br_c']),
 'DoM_Delay': dict(ld=Lw+['load_op_add','load_cmov','prefetch'],str=['store','store8','store16','store32'],
              other_n=['bitnot','add','zsm','div','mov','shl_imm'],other_x=['zsm','div'],br=['br_c']),
 'STL':   dict(ld=Lw+['load_op_add'],str=['store','store8','store16','store32','store_imm'],
              other_n=['bitnot','add','zsm','mov','addq','xor'],other_x=['zsm','div'],br=['br_c']),
}
CAT={'ld':'ld','str':'str','other_n':'other_n','other_x':'other_x','br_n':'br','br_x':'br'}
def recs(xmls):
    out=[]
    for x in xmls:
        r1=P.pass1_specify_state_a(P.parse_alloy_xml(open(x).read()),write_out=False)
        out.append([(r['kind'],{s['slot'] for v in r['slots'].values() for s in v if s['specified']}) for r in r1['instructions']])
    return out
def combos(inst,tab):
    prod=1
    for k,spec in inst:
        c=CAT.get(k,'other_n'); cands=tab[c]
        valid=[n for n in cands if spec<=U[n]] or cands
        prod*=len(valid)
    return prod
def summ(xs):
    xs=sorted(xs); g=math.exp(sum(map(math.log,xs))/len(xs))
    return f"median {xs[len(xs)//2]}, mean {sum(xs)/len(xs):.1f}, geomean {g:.1f}, max {xs[-1]}"
corp={'real6':[R+p for p in ['testsets/DEMO_corpus/xml/inst-047231.xml','wiki/findings/bug/recon_SLF_stlf_bypass/inst-014912.xml',
        'testsets/STT_6__twophase_draft/stage1_xml/inst-000001.xml','testsets/STT_6__twophase_draft/stage1_xml/inst-000002.xml',
        'testsets/Recon_6__twophase_draft/stage1_xml/inst-000001.xml','testsets/Recon_6__twophase_draft/stage1_xml/inst-000002.xml']],
      'draft458':sorted(glob.glob(R+'results/twophase_stage1_2026-11-03/tiny/out_*_N[35]/inst-*.xml'))}
corp['draft458']=[x for x in corp['draft458'] if 'core' not in x]
for cn,xs in corp.items():
    rs=recs(xs); kinds=collections.Counter(k for i in rs for k,_ in i)
    print(f"== corpus {cn}: {len(xs)} instances, records per kind {dict(kinds)}")
    for tn,tab in T.items():
        sizes={k:len(v) for k,v in tab.items()}
        print(f"  {tn:15s} sizes {sizes}  combos/instance: {summ([combos(i,tab) for i in rs])}")
