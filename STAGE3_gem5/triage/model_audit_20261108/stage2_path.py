#!/usr/bin/env python3
# Usage: python3 -I stage2_path.py <xml-dir> <limit> [interleave-cfg-json | -]   Runs parsexml passes 1-3 (+interleave) like batch_generate and traces register/memory def-use of the concretised program. Imports parsexml from the repo path below (read-only). MODEL_AUDIT_SPT_RECON.md Q2(b), Q3.
"""stage2_path.py XMLDIR LIMIT [interleave_cfg_json|-] -- post-Stage-2 (pass1..pass4) register/memory
def-use trace of the CONCRETIZED program (real x86 registers + memory offsets, after interleave).
Reports: ALU op on the xm leak operand's backward cone (and whether a load feeds it); synthetic
(interleave) instruction on the cone; synthetic transmitters placed BEFORE the first unresolved
Alloy branch (non-speculative) whose address register was last written by an Alloy instruction
(a declassification hazard under SPT). Read-only use of STAGE2_compilation/parsexml.py.
model-audit 2026-11-08."""
import sys, json, random, zlib, glob, os, collections
sys.path.insert(0, '/Users/annaeaton/trippel/simspect/STAGE2_compilation')
import parsexml as P
xdir, limit = sys.argv[1], int(sys.argv[2])
icfg = json.loads(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != '-' else None
mode = 'mispredict_not_taken'
ALU = {'other_n', 'other_x'}
C = collections.Counter(); ex = collections.defaultdict(list)
def reads(rec):
    r = []; m = []
    for role, sl in rec['slots'].items():
        for s in sl:
            if role in ('inreg', 'inaddr') and s.get('assigned'): r.append((s['slot'], s['assigned']))
            if role == 'inmem' and s.get('assigned_offset') is not None: m.append(s['assigned_offset'])
    return r, m
def writes(rec):
    r = []; m = []
    for role, sl in rec['slots'].items():
        for s in sl:
            if role == 'outreg' and s.get('assigned'): r.append(s['assigned'])
            if role == 'outmem' and s.get('assigned_offset') is not None: m.append(s['assigned_offset'])
    return r, m
files = sorted(glob.glob(os.path.join(xdir, 'inst-*.xml')))[:limit]
for f in files:
    stem = os.path.basename(f)[:-4]
    inst = P.parse_alloy_xml(open(f).read())
    r1 = P.pass1_specify_state_a(inst, write_out=False)
    nv = int(icfg.get('variants_per_instance', 1)) if icfg and icfg.get('enabled') else 1
    for v in range(nv):
        vseed = zlib.crc32(f"{stem}_v{v}".encode()); random.seed(vseed)
        try:
            r2 = P.pass2_specify_instructions(r1, write_out=False)
            r25 = P.pass2_5_specify_branches(r2, branch_mode=mode, write_out=False)
            rng = random.Random(vseed ^ 0xABCD_1234)
            ril = P.pass_interleave(r25, icfg, rng)
            r3 = P.pass3_assign_operands(ril, write_out=False)
        except NotImplementedError:
            C['skip'] += 1; continue
        ins = r3['instructions']; C['programs'] += 1
        lastw_r = {}; lastw_m = {}; dep = {}; vdep = {}  # pc -> producer pcs (all reads) / value-only reads
        first_unres = None
        for k, rec in enumerate(ins):
            rr, mm = reads(rec)
            dep[k] = [lastw_r[x] for _, x in rr if x in lastw_r] + [lastw_m[o] for o in mm if o in lastw_m]
            vdep[k] = ([lastw_m[o] for o in mm if o in lastw_m] if rec['kind'] == 'ld'
                       else [lastw_r[x] for s_, x in rr if x in lastw_r and not (rec['kind'] == 'str' and s_ == 'inaddr')])
            if rec['kind'] in ('br_n', 'br_x') and not rec.get('resolved') and not rec.get('synthetic') and first_unres is None:
                first_unres = k
            # synthetic transmitter before the first unresolved branch reading an Alloy-written register
            if rec.get('synthetic') and rec['kind'] in ('ld', 'str') and (first_unres is None):
                addr = [x for s_, x in rr if s_ == 'inaddr']
                if any(a in lastw_r and not ins[lastw_r[a]].get('synthetic') for a in addr):
                    C['synthetic_nonspec_xmit_reads_alloy_value'] += 1
                    for a in addr:
                        if a in lastw_r and not ins[lastw_r[a]].get('synthetic'):
                            pr = ins[lastw_r[a]]
                            locked = set(r3['locked_registers'].values())
                            rr2, _ = reads(pr)
                            C['  producer=%s reads_locked=%s' % (pr.get('concrete_instruction'), any(x in locked for _, x in rr2))] += 1
                    if len(ex['nsx']) < 3: ex['nsx'].append(f"{stem}_v{v}@{k}")
            wr, wm = writes(rec)
            for x in wr: lastw_r[x] = k
            for o in wm: lastw_m[o] = k
        # xm cone
        xk = [k for k, rec in enumerate(ins) if rec.get('xm')]
        if not xk: C['no_xm'] += 1; continue
        x = xk[0]; xr = ins[x]
        # leak operand(s) of xm
        rr, mm = reads(xr)
        want = {'ld': ('inaddr',), 'str': ('inaddr',), 'br_x': ('inreg0', 'inreg1')}.get(xr['kind'], ())
        # re-trace producers of the leak operand only
        lastw_r = {}; lastw_m = {}
        prod_of = {}
        for k, rec in enumerate(ins[:x]):
            wr, wm = writes(rec)
            for r_ in wr: lastw_r[r_] = k
            for o in wm: lastw_m[o] = k
        start = [lastw_r[r_] for s_, r_ in rr if s_ in want and r_ in lastw_r]
        cone = set(); st = list(start)
        while st:
            k = st.pop()
            if k in cone: continue
            cone.add(k); st.extend(dep[k])
        alu = [k for k in cone if ins[k]['kind'] in ALU]
        vcone = set(); st = list(start)
        while st:
            k = st.pop()
            if k in vcone: continue
            vcone.add(k); st.extend(vdep[k])
        if any(ins[k]['kind'] in ALU for k in vcone): C['VALUE_alu_on_xm_path'] += 1
        if any(ins[k]['kind'] in ALU and any(ins[j]['kind'] == 'ld' for j in vcone if j < k) for k in vcone):
            C['VALUE_load_then_alu_on_xm_path'] += 1
            if len(ex['valu']) < 4: ex['valu'].append(f"{stem}_v{v}")
        if any(ins[k].get('synthetic') and ins[k]['kind'] != 'other_n' or (ins[k].get('synthetic') and ins[k]['kind'] == 'other_n' and ins[k].get('instruction','').startswith('_chain')) for k in vcone):
            C['VALUE_chain_step_on_xm_path'] += 1
            if len(ex['vsyn']) < 4: ex['vsyn'].append(f"{stem}_v{v}")
        C['xm_' + xr['kind']] += 1
        if alu: C['alu_on_xm_path'] += 1
        if any(ins[k]['kind'] == 'ld' for k in cone):
            C['load_on_xm_path'] += 1
        if any(ins[k]['kind'] in ALU and any(ins[j]['kind'] == 'ld' for j in cone if j < k) for k in cone):
            C['load_then_alu_on_xm_path'] += 1
            if len(ex['alu']) < 3: ex['alu'].append(f"{stem}_v{v}")
        if any(ins[k].get('synthetic') for k in cone):
            C['synthetic_on_xm_path'] += 1
            if len(ex['syn']) < 3: ex['syn'].append(f"{stem}_v{v}")
        if any(ins[k].get('synthetic') for k in range(len(ins))): C['has_synthetic'] += 1
        if not start: C['xm_leakop_unfed_in_program'] += 1
print(json.dumps({'xml_dir': xdir, 'interleave': bool(icfg and icfg.get('enabled')), 'counts': dict(C), 'examples': ex}, indent=1))
