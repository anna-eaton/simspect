#!/bin/bash
# Usage: ./run_mf_list2.sh <RUNLIST.tsv> [name-regex]   like run_mf_list.sh, and also accepts "RFP:<abs path.als>" entries (run as is).
D=/Users/annaeaton/trippel/simspect/STAGE3_gem5/triage/model_audit_20261108
echo "=== run_mf_list2 begin $(date '+%F %T') $1 ${2:-all}" >> $D/queries/model_fixes_runs.log
while IFS=$'\t' read -r name lim to exp; do
  [[ -n "$2" && ! "$name" =~ $2 ]] && continue
  if [[ "$name" == RFP:* ]]; then f="${name#RFP:}"; $D/runq_mf.sh "$f" $lim $to "rf_patched/$(basename $f) [expect: $exp]"
  else $D/runq_mf.sh $D/queries/mf/$name.als $lim $to "$name [expect: $exp]"; fi
done < "$1"
echo "=== run_mf_list2 end $(date '+%F %T')" >> $D/queries/model_fixes_runs.log
