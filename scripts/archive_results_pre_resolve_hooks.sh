#!/bin/bash
# Archive every results/ campaign produced before the 2026-10-30 harness fixes
# (branch-ann alias, derived branch force, resolve hooks, lc/fnc pinning) into
# one zip and verify it. With --delete (Anna runs this herself), it then
# deletes the bulky outputs from results/ after re-verifying the zip.
# Kept in place: run_config*.jsonc, *.md, diagnostics/ (scripts + bug mds), *.py.
# Skipped entirely: dirs given in SKIP (live work of other sessions).
# Usage (in the gem5_dev container): scripts/archive_results_pre_resolve_hooks.sh [--delete]
# Log: /tests/simspect/archive/results_pre_resolve_hooks_20261030.log
set -u
cd /tests/simspect || exit 1
A=archive; mkdir -p $A
Z=$A/results_pre_resolve_hooks_20261030.zip
LOG=$A/results_pre_resolve_hooks_20261030.log
SKIP="STT_6_stl_hooktest"
exec >> $LOG 2>&1
echo "[$(date -Iseconds)] START"
df -h /tests | tail -1
list=$(ls -d results/* results/.[!.]* 2>/dev/null | while read d; do b=$(basename $d); case " $SKIP " in *" $b "*) ;; *) echo $d;; esac; done)
n_src=$(find $list -type f | wc -l); b_src=$(find $list -type f -printf '%s\n' | awk '{s+=$1} END {print s}')
echo "source: $n_src files, $b_src bytes"
if [ "${1:-}" != "--delete" ] || [ ! -e $Z ]; then
  zip -q -r -y $Z $list || { echo "zip FAILED"; exit 1; }
fi
unzip -tq $Z || { echo "unzip -t FAILED"; exit 1; }
n_zip=$(unzip -Z1 $Z | grep -v '/$' | wc -l); b_zip=$(unzip -Zt $Z | awk '{print $3}')
echo "zip: $n_zip entries, $b_zip bytes uncompressed, $(stat -c %s $Z) bytes on disk"
if [ "$n_zip" -lt "$n_src" ]; then echo "COUNT MISMATCH: not deleting"; exit 1; fi
if [ "${1:-}" != "--delete" ]; then echo "zip verified; originals left in place (rerun with --delete to remove them)"; echo "[$(date -Iseconds)] END"; exit 0; fi
find $list -type f ! -name 'run_config*.jsonc' ! -name '*.md' ! -name '*.py' ! -path '*/diagnostics/*' -delete
find $list -depth -type d -empty -delete
echo "after delete: $(find $list -type f 2>/dev/null | wc -l) files kept"
df -h /tests | tail -1
echo "[$(date -Iseconds)] END"
