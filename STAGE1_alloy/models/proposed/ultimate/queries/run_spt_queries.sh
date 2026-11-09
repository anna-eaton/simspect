#!/bin/bash
# run_spt_queries.sh -- run SPT-agent Alloy query files under the shared one-java lock (2026-11-09).
# Usage: bash run_spt_queries.sh <timeout_s> <file.als> [<file.als> ...]
#        MODE=models LIMIT=<n> bash run_spt_queries.sh <timeout_s> <file.als>   (a6CountModels: dump the
#        FIRST command's instances, up to LIMIT, into spt_out/<name>.out/)
#        MODE=count LIMIT=<n> ...   (a6CountOnly: count the FIRST command's instances up to LIMIT; an
#        empty/short COUNT line after rc=124 means the timeout hit before the count finished)
# Default MODE=all runs every command of each file in ONE JVM with a6RunAll (this directory), which prints
# `CMD <label> SAT|UNSAT <ms>` per command (count_* labels: COUNT <n> EXHAUSTED|CAPPED) and writes the
# witness of every SAT command to spt_out/<name>/<label>.{txt,xml}.
# Lock: waits for mkdir of the shared alloy.lock AND for no other java process (another agent's run),
# holds the lock for the whole batch, releases it on any exit. Each file runs under gtimeout -k 10.
# Log: one line per file and per command to spt_runs.log here (UTC start/end, file, rc, secs; rc 124 =
# timeout, the lines printed before the kill are kept). Raw java output: spt_out/<name>.log.
set -u
SK=/private/tmp/claude-501/-Users-annaeaton-Documents-stanford-trippel-simspect/3e17c539-dd1e-4f38-805e-ce336a0f23ff/scratchpad/agents
LOCK=$SK/alloy.lock
REPO=/Users/annaeaton/Documents/stanford/trippel/simspect
Q=$REPO/STAGE1_alloy/models/proposed/ultimate/queries
# run from a private snapshot of this script, so editing the file never disturbs a queued run
if [ -z "${SPT_RUNNER_COPY:-}" ]; then
  mkdir -p "$SK/spt"; snap=$(mktemp "$SK/spt/run_spt_queries.XXXXXX"); cp "$0" "$snap"
  SPT_RUNNER_COPY=1 exec bash "$snap" "$@"
fi
JAVA=/opt/homebrew/opt/openjdk@17/bin/java
LOG=$Q/spt_runs.log
OUT=$Q/spt_out
MODE=${MODE:-all}; LIMIT=${LIMIT:-200}
TO=$1; shift
mkdir -p "$OUT"
echo "$(date -u +%FT%TZ) WAIT lock+java for: $* (mode=$MODE timeout=$TO)" >> "$LOG"
until mkdir "$LOCK" 2>/dev/null; do sleep 15; done
jpid=""
# never leave java running: a TERM/INT/HUP to this runner stops gtimeout (which forwards it to java)
trap 'rmdir "$LOCK" 2>/dev/null; echo "$(date -u +%FT%TZ) RELEASED lock" >> "$LOG"' EXIT
trap '[ -n "$jpid" ] && kill -TERM "$jpid" 2>/dev/null; wait "$jpid" 2>/dev/null; echo "$(date -u +%FT%TZ) KILLED by signal" >> "$LOG"; exit 143' INT TERM HUP
waited=0
while pgrep -f "java .*alloy6" >/dev/null; do sleep 15; waited=$((waited+15)); done
echo "$(date -u +%FT%TZ) ACQUIRED lock (waited ${waited}s for other java)" >> "$LOG"
# resolve every argument to an absolute path BEFORE changing directory
files=()
for f in "$@"; do files+=("$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"); done
cd "$REPO/STAGE1_alloy"
for fa in "${files[@]}"; do
  name=$(basename "$fa" .als)
  start=$(date +%s); stamp=$(date -u +%FT%TZ)
  if [ "$MODE" = count ]; then
    gtimeout -k 10 "$TO" "$JAVA" -Xmx6g -cp alloy6.jar:. a6CountOnly "$fa" "$LIMIT" > "$OUT/$name.log" 2>&1 &
    jpid=$!; wait "$jpid"; rc=$?; jpid=""
    echo "COUNT $(grep -a -v 'INFO kodkod' "$OUT/$name.log" | tail -1)" >> "$OUT/$name.log"
  elif [ "$MODE" = models ]; then
    rm -rf "$OUT/$name.out"
    gtimeout -k 10 "$TO" "$JAVA" -Xmx6g -cp alloy6.jar:. a6CountModels "$fa" "$OUT/$name.out" "$LIMIT" > "$OUT/$name.log" 2>&1 &
    jpid=$!; wait "$jpid"; rc=$?; jpid=""
  else
    rm -rf "$OUT/$name"
    gtimeout -k 10 "$TO" "$JAVA" -Xmx6g -cp "alloy6.jar:$Q" a6RunAll "$fa" "$OUT/$name" "$LIMIT" > "$OUT/$name.log" 2>&1 &
    jpid=$!; wait "$jpid"; rc=$?; jpid=""
  fi
  secs=$(( $(date +%s) - start ))
  echo "$stamp FILE $name mode=$MODE limit=$LIMIT timeout=$TO rc=$rc secs=$secs" >> "$LOG"
  grep -a -E "^CMD |Total models|DONE|^COUNT" "$OUT/$name.log" | sed "s/^/    $name: /" >> "$LOG"
  if [ $rc -ne 0 ] && [ $rc -ne 124 ]; then
    grep -a -m5 -i -E "error|exception|syntax|type" "$OUT/$name.log" | sed "s/^/    ERR $name: /" >> "$LOG"
  fi
done
