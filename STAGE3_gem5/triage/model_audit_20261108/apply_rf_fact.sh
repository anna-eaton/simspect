#!/bin/bash
# Usage (Anna runs it; the model-fixes agent did NOT): bash STAGE3_gem5/triage/model_audit_20261108/apply_rf_fact.sh
# Applies rf_from_most_recent_writer (verbatim STT_6.als:161-169, inserted after `fact same_state_rf`) IN PLACE to the
# 7 in-use models listed in results/model_fixes_20261108/rf_patched/HASHES.txt. For each file it refuses unless the
# current sha256 equals the recorded OLD hash, copies the pre-built patched copy over it, and checks the NEW hash.
# Diffs: results/model_fixes_20261108/rf_patched/*.diff and wiki/state/ALLOY_MODEL_CHANGES.md "2026-11-08 — model-fixes".
set -euo pipefail
ROOT=/Users/annaeaton/trippel/simspect; R=$ROOT/results/model_fixes_20261108/rf_patched
while read -r f old new; do
  cur=$(shasum -a 256 "$ROOT/STAGE1_alloy/models/$f" | cut -c1-64)
  [ "$cur" = "$old" ] || { echo "SKIP $f: current sha $cur != recorded old $old (file changed since the diff was made)"; continue; }
  cp "$R/$(basename $f)" "$ROOT/STAGE1_alloy/models/$f"
  [ "$(shasum -a 256 "$ROOT/STAGE1_alloy/models/$f" | cut -c1-64)" = "$new" ] && echo "APPLIED $f  $old -> $new" || echo "ERROR $f: new hash mismatch"
done < "$R/HASHES.txt"
