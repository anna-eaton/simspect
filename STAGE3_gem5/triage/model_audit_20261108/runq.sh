#!/bin/bash
# Usage: ./runq.sh <query.als (absolute)> <outdir (absolute)> <limit> <timeout_s>   Runs a6CountModels from STAGE1_alloy with Java 17 under gtimeout; prints rc, seconds, "Total models: N" (0 with rc=0 = exhausted/UNSAT). One Java at a time.
cd /Users/annaeaton/trippel/simspect/STAGE1_alloy
start=$(date +%s)
gtimeout $4 /opt/homebrew/opt/openjdk@17/bin/java -Xmx4g -cp alloy6.jar:. a6CountModels "$1" "$2" "$3" > "$2.log" 2>&1
rc=$?
echo "rc=$rc secs=$(( $(date +%s) - start )) $(tail -1 $2.log)"
