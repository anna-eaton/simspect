#!/bin/bash
# SimSpect hooks v2 (2026-11-07): rerun every verification case against the v2
# binaries, with REFERENCE binaries that have the same non-print code (v1 hooks +
# resolve hooks + the 2026-10-30 IEW wake fix, built by
# /work/amulet/hooks_v2_work/make_refs.sh), then run check_v2_trace.py on each
# new trace. Doc: wiki/design/SIMSPECT_HOOKS.md ("How to verify").
# Run inside gem5_dev from a dir holding verify_simspect_hooks.py, check_v2_trace.py,
# mkann.py, uv6x.s, uv6dep.s (cafe2: /work/amulet/simspect_hooks_verify_v2).
# Writes <case>/ dirs, <case>.log, <case>.check.json; prints one line per case.
set -u
V=python3
A=/work/amulet
W=$A/hooks_v2_work
R=/tests/simspect
T=$R/testsets/STT_6/mispredict_not_taken
C=$R/results/STT_6_cleanupspec_residue
INV=$A/amulet-gem5-InvisiSpec_AE-v1.1; CLN=$A/amulet-gem5-CleanupSpec_AE-v1.1; LFB=$A/amulet-gem5-SpecLFB_AE-v1.1
RB=build/X86_MESI_Two_Level/gem5.opt; CB=build/X86/gem5.opt
INVREF=$W/ref_InvisiSpec/$RB; CLNREF=$W/ref_CleanupSpec/$RB
LFBREF=$LFB/$CB.simspect-hooks-v1-resolve-wake-20261030
ISX="--ruby --scheme=SpectreSafeInvisibleSpec --needsTSO=1 --allowSpecBuffHit=1 --l1d_size=1kB --l1d_assoc=2"
FSX="--ruby --scheme=FuturisticSafeInvisibleSpec --needsTSO=1 --allowSpecBuffHit=1 --l1d_size=1kB --l1d_assoc=2"
CSX="--ruby --l2cache --scheme_invisispec=UnsafeBaseline --scheme_cleanupcache=Cleanup_FOR_L1L2 --needsTSO=0"

run() {  # name build bin ref se s ann stall extra
  local n=$1 b=$2; shift 2
  $V verify_simspect_hooks.py --bin "$1" ${2:+--ref-bin "$2"} --se "$3" --s "$4" --ann "$5" --stall "$6" --extra="$7" --out "$n" > "$n.log" 2>&1
  local rc=$?
  $V check_v2_trace.py "$n/new/pipeview.txt" --build "$b" > "$n.check.json" 2>&1
  local crc=$?
  echo "$n rc=$rc check=$crc $(python3 -c "import json;d=json.load(open('$n/summary.json'));c=json.load(open('$n.check.json'));print('ok=%s ticks=%s/%s same=%s pp_same=%s kinds=%d hard=%s' % (d['ok'],d.get('sim_ticks_new'),d.get('sim_ticks_ref'),d.get('non_simspect_identical'),d.get('parse_pipeview_identical'),len(d['kinds']),[k for k,v in c['hard'].items() if not v] or 'all-pass'))" 2>&1)"
}
echo "[$(date -Iseconds)] START run_all_verify_v2"
run inv_uv1 InvisiSpec $INV/$RB $INVREF $INV/configs/example/se.py $T/asm/inst-002014.s $T/ann/inst-002014.ann.json 5000 "$ISX"
run inv_fut InvisiSpec $INV/$RB $INVREF $INV/configs/example/se.py $T/asm/inst-002014.s $T/ann/inst-002014.ann.json 5000 "$FSX"
run inv_014986 InvisiSpec $INV/$RB $INVREF $INV/configs/example/se.py $T/asm/inst-014986.s $T/ann/inst-014986.ann.json 5000 "$ISX"
for g in uv4align uv4split; do
  BR=$(python3 -c "import json;print(hex(json.load(open('$C/uv4_demo/$g.ann.json'))['annotations'][0]['branch_addr']))")
  run cln_$g CleanupSpec $CLN/$RB $CLNREF $CLN/configs/example/se.py $C/uv4_demo/$g.s $C/uv4_demo/$g.ann.json 2000 "$CSX --fnc-commit-stall-pc=$BR --fnc-commit-stall-cycles=150"
done
BR=$(python3 mkann.py $C/uv5_demo/uv5clean.s)
run cln_uv5clean CleanupSpec $CLN/$RB $CLNREF $CLN/configs/example/se.py $C/uv5_demo/uv5clean.s uv5clean.ann.json 2000 "$CSX --l1d_size=8kB --l1d_assoc=2 --L1_TBEs=8 --fnc-commit-stall-pc=$BR --fnc-commit-stall-cycles=150"
run cln_inst002014 CleanupSpec $CLN/$RB $CLNREF $CLN/configs/example/se.py $T/asm/inst-002014.s $T/ann/inst-002014.ann.json 5000 "$CSX"
python3 mkann.py uv6x.s > /dev/null
run lfb_uv6x SpecLFB $LFB/$CB $LFBREF $LFB/configs/example/se.py uv6x.s uv6x.ann.json 2000 "--l2cache"
python3 mkann.py uv6dep.s > /dev/null
run lfb_uv6dep SpecLFB $LFB/$CB $LFBREF $LFB/configs/example/se.py uv6dep.s uv6dep.ann.json 2000 "--l2cache"
run lfb_inst002014 SpecLFB $LFB/$CB $LFBREF $LFB/configs/example/se.py $T/asm/inst-002014.s $T/ann/inst-002014.ann.json 5000 "--l2cache"
echo "[$(date -Iseconds)] END run_all_verify_v2"
