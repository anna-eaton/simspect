#!/bin/bash
# runq_u.sh <query.als> <limit> <timeout_s> [count|models]
# One Alloy run under the shared one-java lock. Prints and appends to runs.log:
# rc (124 = timeout), seconds, last line of the java output ("N" for a6CountOnly,
# "Total models: N" for a6CountModels). For a `check` command N = #counterexamples
# found (0 with rc=0 = the assertion holds at that scope). For a `run`, 0 with
# rc=0 = UNSAT (exhausted). Exit 75 = lock busy (nothing run).
SK=/private/tmp/claude-501/-Users-annaeaton-Documents-stanford-trippel-simspect/3e17c539-dd1e-4f38-805e-ce336a0f23ff/scratchpad/agents
LOCK=$SK/alloy.lock
SCR=$SK/skeleton/runs
REPO=/Users/annaeaton/Documents/stanford/trippel/simspect
LOG=$REPO/STAGE1_alloy/models/proposed/ultimate/queries/runs.log
Q=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); LIM=$2; TO=$3; MODE=${4:-count}
mkdir -p "$SCR"
mkdir "$LOCK" 2>/dev/null || { echo BUSY; exit 75; }
trap 'rmdir "$LOCK"' EXIT
cd $REPO/STAGE1_alloy
name=$(basename "$Q" .als)
start=$(date +%s)
if [ "$MODE" = models ]; then
  rm -rf "$SCR/$name.out"
  gtimeout -k 10 "$TO" /opt/homebrew/opt/openjdk@17/bin/java -Xmx4g -cp alloy6.jar:. a6CountModels "$Q" "$SCR/$name.out" "$LIM" > "$SCR/$name.log" 2>&1
else
  gtimeout -k 10 "$TO" /opt/homebrew/opt/openjdk@17/bin/java -Xmx4g -cp alloy6.jar:. a6CountOnly "$Q" "$LIM" > "$SCR/$name.log" 2>&1
fi
rc=$?
secs=$(( $(date +%s) - start ))
res=$(grep -v "INFO kodkod" "$SCR/$name.log" | tail -1)
line="$(date -u +%FT%TZ) $name limit=$LIM timeout=$TO mode=$MODE rc=$rc secs=$secs result=[$res]"
echo "$line" >> "$LOG"
echo "$line"
