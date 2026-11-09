# Usage: python3 -I show_prog.py <inst-N.xml> <variant> [interleave-cfg-json]   Prints the concretised (pass 3) program of one test variant, registers/offsets per slot (* = Alloy-specified).
import sys, json, random, zlib
sys.path.insert(0, '/Users/annaeaton/trippel/simspect/STAGE2_compilation')
import parsexml as P
f, v = sys.argv[1], int(sys.argv[2]); icfg = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
stem = f.split('/')[-1][:-4]
inst = P.parse_alloy_xml(open(f).read()); r1 = P.pass1_specify_state_a(inst, write_out=False)
vseed = zlib.crc32(f"{stem}_v{v}".encode()); random.seed(vseed)
r2 = P.pass2_specify_instructions(r1, write_out=False)
r25 = P.pass2_5_specify_branches(r2, branch_mode='mispredict_not_taken', write_out=False)
ril = P.pass_interleave(r25, icfg, random.Random(vseed ^ 0xABCD_1234))
r3 = P.pass3_assign_operands(ril, write_out=False)
for rec in r3['instructions']:
    sl = []
    for role, l in rec['slots'].items():
        for s in l:
            a = s.get('assigned') if role in ('inreg','inaddr','outreg') else s.get('assigned_offset')
            if a is not None: sl.append(f"{s['slot']}={a}{'*' if s.get('specified') else ''}")
    print(rec['pc'], rec['instruction'], rec['kind'], rec.get('concrete_instruction'), 'R' if rec.get('resolved') else 'u', 'C' if rec.get('committed') else '-', 'XM' if rec.get('xm') else '', ' '.join(sl))
