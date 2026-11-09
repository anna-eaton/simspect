#!/bin/bash
# batch_u.sh <list.tsv>   lines: <query.als> <limit> <timeout_s> <count|models>
# Runs each query through runq_u.sh, waiting (polling every 10 s, up to 3 h per query)
# while another agent holds the one-java lock; the lock is released between queries.
cd "$(dirname "$0")"
while read -r q lim to mode; do
  [ -z "$q" ] && continue; case "$q" in \#*) continue;; esac
  waited=0
  while true; do
    ./runq_u.sh "$q" "$lim" "$to" "$mode"; rc=$?
    [ $rc -ne 75 ] && break
    sleep 10; waited=$((waited+10))
    if [ $waited -gt 10800 ]; then echo "$(date -u +%FT%TZ) $q GAVE-UP waiting for lock" | tee -a runs.log; break; fi
  done
done < "$1"
echo BATCH-DONE "$1"
