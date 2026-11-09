import sys, json
sys.path.insert(0, '/Users/annaeaton/trippel/simspect/STAGE3_gem5')
import gem5_common as gc, check_footprint as cf
from pathlib import Path
p = Path(sys.argv[1]); meta = json.load(open(sys.argv[2]))
crit = cf.load_criterion('/Users/annaeaton/trippel/simspect/specs/leakage/invisispec.json')
pv = gc.parse_pipeview_by_seq(p)
for s in range(540, 600):
    if s in pv:
        r = pv[s]; print(s, {k: r[k] for k in r if k not in ('disasm',)}, r.get('disasm',''))
res = cf.evaluate_trace(p, crit, meta['lc_pc'], meta['fnc_pc'], meta['unresolved'], meta['ticks_per_cycle'], scheme_name='SpectreSafeInvisibleSpec')
print(json.dumps(res, indent=1, default=str)[:6000])
