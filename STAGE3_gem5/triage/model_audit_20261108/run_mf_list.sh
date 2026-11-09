#!/bin/bash
# Usage: ./run_mf_list.sh <RUNLIST.tsv> [name-regex]   runs each listed query (queries/mf/<name>.als) via runq_mf.sh, sequentially.
D=/Users/annaeaton/trippel/simspect/STAGE3_gem5/triage/model_audit_20261108
echo "=== run_mf_list begin $(date '+%F %T') $1 ${2:-all}" >> $D/queries/model_fixes_runs.log
while IFS=$'\t' read -r name lim to exp; do
  [[ -n "$2" && ! "$name" =~ $2 ]] && continue
  $D/runq_mf.sh $D/queries/mf/$name.als $lim $to "$name [expect: $exp]"
done < "$1"
echo "=== run_mf_list end $(date '+%F %T')" >> $D/queries/model_fixes_runs.log
