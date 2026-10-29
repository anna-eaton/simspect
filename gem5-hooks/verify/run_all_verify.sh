#!/bin/bash
# Re-run every SimSpect-hooks verification case (wiki/design/SIMSPECT_HOOKS.md "How to verify").
# Run inside gem5_dev from a dir holding verify_simspect_hooks.py, mkann.py, uv6x.s
# (cafe2: /work/amulet/simspect_hooks_verify). Writes <case>/ dirs + <case>.log; prints a table.
set -u
V=python3
A=/work/amulet
R=/tests/simspect
T=$R/testsets/STT_6/mispredict_not_taken
C=$R/results/STT_6_cleanupspec_residue
INV=$A/amulet-gem5-InvisiSpec_AE-v1.1; CLN=$A/amulet-gem5-CleanupSpec_AE-v1.1; LFB=$A/amulet-gem5-SpecLFB_AE-v1.1
RB=build/X86_MESI_Two_Level/gem5.opt; CB=build/X86/gem5.opt; PRE=.pre-simspect-hooks-20261028
ISX="--ruby --scheme=SpectreSafeInvisibleSpec --needsTSO=1 --allowSpecBuffHit=1 --l1d_size=1kB --l1d_assoc=2"
CSX="--ruby --l2cache --scheme_invisispec=UnsafeBaseline --scheme_cleanupcache=Cleanup_FOR_L1L2 --needsTSO=0"

run() {  # name bin ref se s ann stall extra
  local n=$1; shift
  $V verify_simspect_hooks.py --bin "$1" ${2:+--ref-bin "$2"} --se "$3" --s "$4" --ann "$5" --stall "$6" --extra="$7" --out "$n" > "$n.log" 2>&1
  echo "$n rc=$? $(python3 -c "import json;d=json.load(open('$n/summary.json'));print('ok=%s ticks=%s/%s same=%s kinds=%d' % (d['ok'],d.get('sim_ticks_new'),d.get('sim_ticks_ref'),d.get('non_simspect_identical'),len(d['kinds'])))")"
}
run inv_uv1  $INV/$RB $INV/$RB$PRE $INV/configs/example/se.py $T/asm/inst-002014.s $T/ann/inst-002014.ann.json 5000 "$ISX"
run inv_fut  $INV/$RB ""          $INV/configs/example/se.py $T/asm/inst-002014.s $T/ann/inst-002014.ann.json 5000 "--ruby --scheme=FuturisticSafeInvisibleSpec --needsTSO=1 --allowSpecBuffHit=1 --l1d_size=1kB --l1d_assoc=2"
for g in uv4align uv4split; do
  BR=$(python3 -c "import json;print(hex(json.load(open('$C/uv4_demo/$g.ann.json'))['annotations'][0]['branch_addr']))")
  run cln_$g $CLN/$RB $CLN/$RB$PRE $CLN/configs/example/se.py $C/uv4_demo/$g.s $C/uv4_demo/$g.ann.json 2000 "$CSX --fnc-commit-stall-pc=$BR --fnc-commit-stall-cycles=150"
done
BR=$(python3 mkann.py $C/uv5_demo/uv5clean.s)
run cln_uv5clean $CLN/$RB $CLN/$RB$PRE $CLN/configs/example/se.py $C/uv5_demo/uv5clean.s uv5clean.ann.json 2000 "$CSX --l1d_size=8kB --l1d_assoc=2 --L1_TBEs=8 --fnc-commit-stall-pc=$BR --fnc-commit-stall-cycles=150"
python3 mkann.py uv6x.s > /dev/null
run lfb_uv6x $LFB/$CB $LFB/$CB$PRE $LFB/configs/example/se.py uv6x.s uv6x.ann.json 2000 "--l2cache"
run lfb_inst002014 $LFB/$CB $LFB/$CB$PRE $LFB/configs/example/se.py $T/asm/inst-002014.s $T/ann/inst-002014.ann.json 5000 "--l2cache"
