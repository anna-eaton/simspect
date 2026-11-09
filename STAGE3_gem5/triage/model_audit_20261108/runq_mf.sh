#!/bin/bash
# Usage: ./runq_mf.sh <query.als (absolute)> <limit> <timeout_s> [label]
# model-fixes (2026-11-08) runner: waits until no other a6Count* java runs on the Mac (one Java at a time),
# then runs a6CountModels from STAGE1_alloy with Java 17 under gtimeout, writing XML to <query>.out/ and the
# java log to <query>.out.log. Appends one line per run to queries/model_fixes_runs.log:
#   <start> <label> <query> limit=<N> rc=<rc> secs=<s> <Total models line>
# "Total models: 0" with rc 0 = exhausted (UNSAT at that scope); rc 124 = timeout.
Q="$1"; LIM="$2"; TO="$3"; LABEL="${4:-$(basename $Q .als)}"
LOG=${MF_LOG:-/Users/annaeaton/trippel/simspect/STAGE3_gem5/triage/model_audit_20261108/queries/model_fixes_runs.log}
while pgrep -f "a6Count" >/dev/null; do sleep 20; done
cd /Users/annaeaton/trippel/simspect/STAGE1_alloy
OUT="${Q%.als}.out"; rm -rf "$OUT"; mkdir -p "$OUT"
start=$(date +%s); stamp=$(date "+%Y-%m-%d %H:%M:%S")
gtimeout $TO /opt/homebrew/opt/openjdk@17/bin/java -Xmx6g -cp alloy6.jar:. a6CountModels "$Q" "$OUT" "$LIM" > "$OUT.log" 2>&1
rc=$?
line="$stamp $LABEL $(basename $Q) limit=$LIM rc=$rc secs=$(( $(date +%s) - start )) $(grep -a 'Total models' $OUT.log | tail -1)"
[ $rc -ne 0 ] && [ $rc -ne 124 ] && line="$line ERR: $(grep -a -m3 -i 'error\|exception' $OUT.log | tr '\n' ' ' | cut -c1-300)"
echo "$line" | tee -a "$LOG"
