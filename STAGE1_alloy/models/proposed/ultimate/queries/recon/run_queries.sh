#!/bin/bash
# run_queries.sh -- run Alloy queries for the ReCon ultimate model, one Java at a time.
# Usage: ./run_queries.sh <RUNLIST.tsv> [name-regex]
#   RUNLIST.tsv lines: name<TAB>limit<TAB>timeout_s<TAB>expectation   (queries are q/<name>.als next to this script)
# Locking: if $ALLOY_LOCK is set, each query first takes that lock directory with mkdir (waiting until it
# succeeds) and removes it right after the query; otherwise it waits until no other a6Count* java runs.
# Each query: a6CountModels (Java 17, -Xmx6g) under gtimeout; XML/txt instances go to q/<name>.out/, the
# java log to q/<name>.out.log. One line per query is appended to runs.log next to this script:
#   <start> <name> limit=<N> rc=<rc> secs=<s> <"Total models" line> | expect: <expectation>
# "Total models: 0" with rc 0 = exhausted (UNSAT at that scope); rc 124 = timeout (no verdict).
HERE="$(cd "$(dirname "$0")" && pwd)"
ST1="$(cd "$HERE/../../../../.." && pwd)"          # STAGE1_alloy
LIST="$1"; PAT="${2:-.}"
LOG="$HERE/runs.log"
JAVA=/opt/homebrew/opt/openjdk@17/bin/java
HELD=; JPID=
cleanup() { [ -n "$JPID" ] && kill "$JPID" 2>/dev/null; [ -n "$HELD" ] && [ -n "$ALLOY_LOCK" ] && rmdir "$ALLOY_LOCK" 2>/dev/null; exit 1; }
trap cleanup INT TERM HUP
while IFS=$'\t' read -r NAME LIM TO EXPECT; do
  [ -z "$NAME" ] && continue
  case "$NAME" in \#*) continue;; esac
  echo "$NAME" | grep -Eq "$PAT" || continue
  Q="$HERE/q/$NAME.als"; OUT="$HERE/q/$NAME.out"
  [ -f "$Q" ] || { echo "missing $Q" | tee -a "$LOG"; continue; }
  if [ -n "$ALLOY_LOCK" ]; then
    # take the lock only when no other Alloy java runs (the mkdir lock has no owner check, so a foreign
    # rmdir can break it); re-check after taking it and back off if another java appeared meanwhile
    while true; do
      while pgrep -f "a6Count" >/dev/null; do sleep 5; done
      until mkdir "$ALLOY_LOCK" 2>/dev/null; do sleep 5; done
      pgrep -f "a6Count" >/dev/null || break
      rmdir "$ALLOY_LOCK" 2>/dev/null; sleep 5
    done
  else
    while pgrep -f "a6Count" >/dev/null; do sleep 10; done
  fi
  HELD=1
  rm -rf "$OUT"; mkdir -p "$OUT"
  start=$(date +%s); stamp=$(date "+%Y-%m-%d %H:%M:%S")
  ( cd "$ST1" && exec gtimeout -k 10 "$TO" "$JAVA" -Xmx6g -cp alloy6.jar:. a6CountModels "$Q" "$OUT" "$LIM" > "$OUT.log" 2>&1 ) &
  JPID=$!; wait $JPID; rc=$?; JPID=
  [ -n "$ALLOY_LOCK" ] && rmdir "$ALLOY_LOCK" 2>/dev/null; HELD=
  line="$stamp $NAME limit=$LIM rc=$rc secs=$(( $(date +%s) - start )) $(grep -a 'Total models' "$OUT.log" | tail -1) | expect: $EXPECT"
  [ $rc -ne 0 ] && [ $rc -ne 124 ] && line="$line ERR: $(grep -a -m3 -i 'error\|exception' "$OUT.log" | tr '\n' ' ' | cut -c1-400)"
  echo "$line" | tee -a "$LOG"
done < "$LIST"
pgrep -f "a6CountModels.*$HERE" >/dev/null && echo "WARNING: a6CountModels still running" | tee -a "$LOG"
exit 0
