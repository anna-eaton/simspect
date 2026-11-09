#!/bin/bash
# stage2_smoke_stt.sh (STT agent 2026-11-09): Stage-2 llvm smoke test of STT_6_u / STT_6_u_stl samples.
# Feeds the a6DumpAll output dirs to STAGE2_compilation/batch_generate.py (passes 1-5 -> .ll + .ann.json; no clang,
# no gem5) with default options (random register naming, default instruction table). Output goes to the scratch dir
# (throwaway); prints per-dir file counts and any traceback lines.
S2=/Users/annaeaton/Documents/stanford/trippel/simspect/STAGE2_compilation/batch_generate.py
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT=/private/tmp/claude-501/-Users-annaeaton-Documents-stanford-trippel-simspect/3e17c539-dd1e-4f38-805e-ce336a0f23ff/scratchpad/agents/stt/s2
rm -rf "$OUT"; mkdir -p "$OUT"
for d in "$HERE"/q_dump.out/dump_gen_first "$HERE"/q_dump.out/dump_R1; do
  n=$(basename "$d"); python3 "$S2" "$d" --out "$OUT/$n" --mode mispredict_not_taken --mode mispredict_taken > "$OUT/$n.log" 2>&1
  echo "$n rc=$? xml=$(ls $d/inst-*.xml 2>/dev/null | wc -l | tr -d ' ') ll_nt=$(ls $OUT/$n/mispredict_not_taken/*.ll 2>/dev/null | wc -l | tr -d ' ') ann_nt=$(ls $OUT/$n/mispredict_not_taken/*.ann.json 2>/dev/null | wc -l | tr -d ' ') ll_t=$(ls $OUT/$n/mispredict_taken/*.ll 2>/dev/null | wc -l | tr -d ' ') errs=$(grep -c -i 'traceback\|error' $OUT/$n.log)"
done
for d in "$HERE"/q_dump_stl.out/dump_stl_first "$HERE"/q_dump_stl.out/dump_stl_S1; do
  n=$(basename "$d"); python3 "$S2" "$d" --out "$OUT/$n" --mode stl_bypass > "$OUT/$n.log" 2>&1
  echo "$n rc=$? xml=$(ls $d/inst-*.xml 2>/dev/null | wc -l | tr -d ' ') ll=$(find $OUT/$n -name '*.ll' | wc -l | tr -d ' ') ann=$(find $OUT/$n -name '*.ann.json' | wc -l | tr -d ' ') errs=$(grep -c -i 'traceback\|error' $OUT/$n.log)"
done
