#!/bin/bash
# crosscheck_stt.sh <dir-with-inst-*.txt | a6RunAll .out dir>  (STT agent 2026-11-09)
# Independent cross-check with the model-fixes Python re-implementation (stt_old = STT_6.als, stt_v2 = STT_6_v2 =
# STT_6_u semantics): STAGE3_gem5/triage/model_audit_20261108/mf_semantics.py. For an a6RunAll .out dir the
# <label>.txt witnesses are copied to a scratch dir as inst-NNNNNN.txt first (mapping printed).
D="$1"; MF=/Users/annaeaton/Documents/stanford/trippel/simspect/STAGE3_gem5/triage/model_audit_20261108/mf_semantics.py
if ls "$D"/inst-*.txt >/dev/null 2>&1; then python3 -I "$MF" "$D"; exit; fi
T=$(mktemp -d /private/tmp/claude-501/-Users-annaeaton-Documents-stanford-trippel-simspect/3e17c539-dd1e-4f38-805e-ce336a0f23ff/scratchpad/agents/stt/xc.XXXX)
n=0; for f in "$D"/*.txt; do n=$((n+1)); cp "$f" "$T/$(printf 'inst-%06d.txt' $n)"; echo "$(printf 'inst-%06d' $n) <- $(basename "$f")"; done
python3 -I "$MF" "$T" --json "$T/rows.json"; python3 -c "
import json; rows=json.load(open('$T/rows.json'))
for r in rows: print(r['inst'], 'old_useful=',r['stt_old'],'v2_useful=',r['stt_v2'],'|',str(r.get('stt_v2_why',''))[:120])"
