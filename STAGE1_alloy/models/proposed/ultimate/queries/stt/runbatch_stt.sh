#!/bin/bash
# runbatch_stt.sh <timeout_s_per_file> <count_limit> <q1.als> [q2.als ...]   (STT ultimate agent, 2026-11-09)
# Takes the Mac-wide Alloy lock ONCE (mkdir; waits while another agent holds it or any java runs),
# runs every command of each file with ../a6RunAll (gtimeout -k 10 per file), releases the lock on exit.
# Per-command results are appended to runs.log next to this script (see runq_stt.sh for the format).
LOCK=/private/tmp/claude-501/-Users-annaeaton-Documents-stanford-trippel-simspect/3e17c539-dd1e-4f38-805e-ce336a0f23ff/scratchpad/agents/alloy.lock
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT=/Users/annaeaton/Documents/stanford/trippel/simspect/STAGE1_alloy
TO="$1"; LIM="$2"; shift 2
until mkdir "$LOCK" 2>/dev/null; do sleep 0.2; done   # the shared protocol: mkdir is the lock
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
echo "=== batch begin $(date '+%Y-%m-%d %H:%M:%S') files: $*" >> "$HERE/runs.log"
for Q in "$@"; do
  case "$Q" in /*) ;; *) Q="$HERE/$Q";; esac
  OUT="${Q%.als}.out"; rm -rf "$OUT"; mkdir -p "$OUT"
  start=$(date +%s); stamp=$(date "+%Y-%m-%d %H:%M:%S")
  gtimeout -k 10 "$TO" /opt/homebrew/opt/openjdk@17/bin/java -Xmx6g -cp "$ROOT/alloy6.jar:$HERE/.." a6RunAll "$Q" "$OUT" "$LIM" > "$OUT.log" 2>&1
  rc=$?
  { echo "$stamp $(basename "$Q") rc=$rc secs=$(( $(date +%s) - start ))"; grep -a "^CMD" "$OUT.log"; [ $rc -ne 0 ] && [ $rc -ne 124 ] && grep -a -m5 -i "error\|exception\|syntax\|type" "$OUT.log"; } >> "$HERE/runs.log"
done
echo "=== batch end $(date '+%Y-%m-%d %H:%M:%S')" >> "$HERE/runs.log"
