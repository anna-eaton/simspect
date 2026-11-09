#!/bin/bash
# runq_stt.sh <query.als (absolute)> <timeout_s> [count_limit]   (STT ultimate agent, 2026-11-09)
# Takes the Mac-wide Alloy lock (one java across all agents), runs every command of the file with
# ../a6RunAll (Java 17, -Xmx6g, gtimeout -k 10), releases the lock on exit, and appends the per-command
# results to runs.log next to this script:  <stamp> <file> rc=<rc> secs=<s>  then one "CMD <label> SAT|UNSAT|COUNT ..." line each.
# rc 124 = whole-file timeout (lines printed before the kill are kept). Output dir: <query>.out/ (witness .txt/.xml per SAT command).
LOCK=/private/tmp/claude-501/-Users-annaeaton-Documents-stanford-trippel-simspect/3e17c539-dd1e-4f38-805e-ce336a0f23ff/scratchpad/agents/alloy.lock
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT=/Users/annaeaton/Documents/stanford/trippel/simspect/STAGE1_alloy
Q="$1"; TO="$2"; LIM="${3:-1000}"
until mkdir "$LOCK" 2>/dev/null; do sleep 10; done
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
OUT="${Q%.als}.out"; rm -rf "$OUT"; mkdir -p "$OUT"
start=$(date +%s); stamp=$(date "+%Y-%m-%d %H:%M:%S")
gtimeout -k 10 "$TO" /opt/homebrew/opt/openjdk@17/bin/java -Xmx6g -cp "$ROOT/alloy6.jar:$HERE/.." a6RunAll "$Q" "$OUT" "$LIM" > "$OUT.log" 2>&1
rc=$?
{ echo "$stamp $(basename "$Q") rc=$rc secs=$(( $(date +%s) - start ))"; grep -a "^CMD" "$OUT.log"; [ $rc -ne 0 ] && [ $rc -ne 124 ] && grep -a -m5 -i "error\|exception" "$OUT.log"; } | tee -a "$HERE/runs.log"
