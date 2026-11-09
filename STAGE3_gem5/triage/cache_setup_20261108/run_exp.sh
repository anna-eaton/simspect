#!/bin/bash
# Cache-setup experiment (2026-11-08, cache-setup session). Run on cafe2 gem5_dev from the tree root
# /tests/simspect_fixed_20261030. Three campaigns on CleanupSpec (footprint config), same 590 stems as the warm
# RMW campaign results/STT_6_rmw_cleanupspec_footprint__20261109_002545:
#   (1) STT_6_rmw cold, (2) plain STT_6 same stems cold, (3) plain STT_6 same stems warm.
# Log: results/STT_6_rmw_cleanupspec_footprint_cold/run_exp.log (start/end/rc per campaign); each testrun.py
# writes its own <results>/testrun.log.
set -u
cd /tests/simspect_fixed_20261030
WARM=results/STT_6_rmw_cleanupspec_footprint__20261109_002545
L=results/STT_6_rmw_cleanupspec_footprint_cold/run_exp.log
mkdir -p results/STT_6_rmw_cleanupspec_footprint_cold
log() { echo "$(date +%F_%T) $*" >> "$L"; }
log "START warm_ref=$WARM"
# Stage the control testsets: symlinks to testsets_latest/STT_6 for exactly the warm run's stems.
for c in ctrl_cold ctrl_warm; do
  for m in mispredict_not_taken mispredict_taken; do
    d=results/STT_6_rmwstems_cleanupspec_footprint_$c/ts/STT_6/$m
    mkdir -p $d/asm $d/ann
    python3 - "$WARM/$m/ld/window-results.json" "$d" "$m" <<'EOF' >> "$L" 2>&1
import json, os, sys
recs = json.load(open(sys.argv[1])); d = sys.argv[2]; m = sys.argv[3]
src = f"/tests/simspect_fixed_20261030/testsets_latest/STT_6/{m}"
n = 0
for r in recs:
    s = r["name"]
    for sub, ext in (("asm", ".s"), ("ann", ".ann.json")):
        p = os.path.join(d, sub, s + ext)
        if not os.path.lexists(p):
            os.symlink(os.path.join(src, sub, s + ext), p)
    n += 1
print(f"staged {n} stems -> {d}")
EOF
  done
done
run() {  # $1 = model, $2 = config, $3 = results name
  mkdir -p results/$3
  log "begin $3 model=$1 config=$2"
  python3 testrun.py --once --model "$1" --config "$2" > results/$3/testrun.log 2>&1
  log "end $3 rc=$?"
}
run STT_6_rmw runconfigs/footprint/run_config_STT_6_rmw_cleanupspec_footprint_cold.jsonc STT_6_rmw_cleanupspec_footprint_cold &
run STT_6 runconfigs/footprint/run_config_STT_6_rmwstems_cleanupspec_footprint_ctrl_cold.jsonc STT_6_rmwstems_cleanupspec_footprint_ctrl_cold &
run STT_6 runconfigs/footprint/run_config_STT_6_rmwstems_cleanupspec_footprint_ctrl_warm.jsonc STT_6_rmwstems_cleanupspec_footprint_ctrl_warm &
wait
log "END"
