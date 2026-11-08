#!/usr/bin/env bash
# Triage driver (2026-11-07): for every br_x hit of an SPT campaign, run the
# x86 condition slice and the gem5-spt pending-squash probe at the hit's grid.
# Usage (in the container, from the fixed repo copy):
#   STAGE3_gem5/triage/run_spt_brx_triage.sh <campaign_dir> <config> <testset_root> <outdir> [jobs]
set -euo pipefail
camp=$1; cfg=$2; ts=$3; out=$4; jobs=${5:-8}
mkdir -p "$out"
echo "[brx-triage] $(date -u '+%F %T') start camp=$camp cfg=$cfg ts=$ts"
python3 STAGE3_gem5/triage/hit_facts.py "$camp" --out "$out/facts.json"
for mode in mispredict_not_taken mispredict_taken; do
  stems=$(python3 - "$out/facts.json" "$mode" <<'PY'
import json, sys
F = json.load(open(sys.argv[1])); g = {}
for f in F:
    if f["kind"] == "br_x" and f["mode"] == sys.argv[2]:
        i = int(f["grid"][4:]); g[f["stem"]] = min(g.get(f["stem"], i), i)
print(" ".join(f"{s}:{i}" for s, i in sorted(g.items())))
PY
)
  [ -z "$stems" ] && continue
  python3 STAGE3_gem5/triage/spt_cond_slice.py "$ts/$mode" $(echo $stems | sed 's/:[0-9]*//g') --out "$out/slice_$mode.json" > "$out/slice_$mode.log" 2>&1
  python3 STAGE3_gem5/triage/spt_taint_probe.py --config "$cfg" --testdir "$ts/$mode" --stems $stems --jobs "$jobs" --out "$out/probe_$mode.json" > "$out/probe_$mode.log" 2>&1
  echo "[brx-triage] $(date -u '+%F %T') $mode done"
done
echo "[brx-triage] $(date -u '+%F %T') end"
