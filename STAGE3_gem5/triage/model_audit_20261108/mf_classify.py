#!/usr/bin/env python3
# Usage: python3 mf_classify.py <query-name> [--show N]   (reads queries/mf/<name>.out/inst-*.txt)
"""mf_classify.py -- explain every instance a model-fixes differential query returned (2026-11-08).
t1_gained / t1_lost      : STT_6 vs STT_6_v2 (cross-checked with mf_semantics.py; reason = the R-1 witness)
t2d2_recon_only          : Recon_6_v2-useful, not STT_6_v2-useful (reason = which perturbation a reveal makes secure)
t2d3_stt_only            : STT_6_v2-useful, not Recon_6_v2-useful (reason = the revealed read on xm's path)
t4_lost / t4_gained      : SPT v2 vs v3 (structural: does a load's value reach a non-speculative transmitter)"""
import sys, glob, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mf_semantics import Inst

name = sys.argv[1]
show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 3
files = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'queries', 'mf', name + '.out', 'inst-*.txt')))
C, EX = collections.Counter(), {}

def pert_reason(I, a, b):
    """first gen perturbation under which semantics a is secure and b is not"""
    for i in I.order:
        if i not in I.resolved and i != I.fu and I.secure(a, RR=[i]) and not I.secure(b, RR=[i]):
            return f'RR->{I.kind[i]}', dict(RR=[i])
    if I.fu is not None and I.secure(a, RR=[I.fu], RC=[I.fu]) and not I.secure(b, RR=[I.fu], RC=[I.fu]):
        return f'RC+RR->first_uncommitted({I.kind[I.fu]})', dict(RR=[I.fu], RC=[I.fu])
    for s in I.states:
        if I.secure(a, RS=[s]) and not I.secure(b, RS=[s]):
            return f'RS->{s.split("$")[0]}', dict(RS=[s])
    return 'NONE', None

for f in files:
    I = Inst(f)
    if name == 't1_gained':
        ok = I.useful('stt_v2')[0] and not I.useful('stt_old')[0]
        w = I.r1_witness()
        key = (ok, 'R-1 witness at no_p' if w else 'NO R-1 WITNESS', I.useful('stt_old')[1])
    elif name == 't1_lost':
        ok = I.useful('stt_old')[0] and not I.useful('stt_v2')[0]
        why, pert = pert_reason(I, 'stt_old', 'stt_v2')
        key = (ok, why, 'R-1 witness under it' if pert and I.r1_witness(**pert) else 'NO R-1 WITNESS')
    elif name == 't2d2_recon_only':
        ok = I.useful('recon_v2')[0] and not I.useful('stt_v2')[0]
        why, pert = pert_reason(I, 'recon_v2', 'stt_v2')
        key = (ok, why, 'revealed read under it' if pert and I.revealed(I.view(**pert)) else 'NO REVEAL')
    elif name == 't2d3_stt_only':
        ok = I.useful('stt_v2')[0] and not I.useful('recon_v2')[0]
        rv = I.revealed(I.view())
        key = (ok, I.useful('recon_v2')[1], 'revealed read at no_p' if rv else 'NO REVEAL AT no_p')
    elif name.startswith('t4_'):
        ns = any(I.K(I.owner[b], 'Load', 'Store') and I.slot[b] == 'inaddr' or I.K(I.owner[b], 'Branchx') and I.slot[b] == 'inreg'
                 for a, b in I.rf if I.slot[a] == 'outreg' and I.K(I.owner[a], 'Load') and I.owner[b] not in I.view()['spec'])
        fwd = any(I.slot[b] == 'inmem' for a, b in I.rf)
        key = ('load value transmitted non-speculatively' if ns else 'NO non-spec transmit of a load value', 'store->load rf present' if fwd else 'no store->load rf')
    else:
        sys.exit('unknown query ' + name)
    C[key] += 1
    EX.setdefault(key, []).append(os.path.basename(f) + '  ' + I.program())

print(f'{name}: {len(files)} instances')
for k, v in C.most_common():
    print(f'  {v:4d}  {k}')
    for e in EX[k][:show]:
        print('        ', e)
