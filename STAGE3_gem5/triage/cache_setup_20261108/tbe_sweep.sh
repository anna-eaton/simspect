#!/bin/bash
# CleanupSpec cold-crash TBE sweep (2026-11-09, cache-random session). Run on cafe2 gem5_dev from the tree root
# /tests/simspect_fixed_20261030. Question: smallest --L2_TBEs (DC_TBEs if needed) at which the cold control
# (plain STT_6, the 590 stems of results/STT_6_rmwstems_cleanupspec_footprint_ctrl_cold/ts) runs without the
# `MESI_Two_Level-L2cache.sm:308` panic (326/590 at L2_TBEs=2), and whether warm hit counts change (UV4 depends on
# TBE pressure). Each arm = the ctrl_cold / ctrl_warm config with only --L2_TBEs/--DC_TBEs (and jobs) changed;
# config saved as results/<arm>/run_config.jsonc, testrun log results/<arm>/testrun.log, sweep log below.
# Usage: tbe_sweep.sh "<l2>:<dc> ..." [jobs]     e.g. tbe_sweep.sh "4:2 8:2 16:2" 6
# Log: results/STT_6_cleanupspec_tbe_sweep_20261109.log (start/end/rc per arm).
set -u
cd /tests/simspect_fixed_20261030
ARMS=${1:-"4:2 8:2 16:2"}
JOBS=${2:-6}
L=results/STT_6_cleanupspec_tbe_sweep_20261109.log
log() { echo "$(date +%F_%T) $*" >> "$L"; }
log "START arms=$ARMS jobs=$JOBS"
run() {  # $1 = l2, $2 = dc, $3 = cold|warm
  local name=STT_6_rmwstems_cleanupspec_tbe_l2_${1}_dc_${2}_${3}
  mkdir -p results/$name
  python3 - "$1" "$2" "$3" "$JOBS" "results/$name/run_config.jsonc" "$name" <<'EOF' >> "$L" 2>&1
import json, re, sys
l2, dc, cs, jobs, out, name = sys.argv[1:]
src = "runconfigs/footprint/run_config_STT_6_rmwstems_cleanupspec_footprint_ctrl_cold.jsonc"
cfg = json.loads("\n".join(l for l in open(src) if not l.lstrip().startswith("//")))
g = cfg["gem5"]
g["extra_args"] = [a for a in g["extra_args"] if not a.startswith(("--L2_TBEs=", "--DC_TBEs="))] + \
                  [f"--L2_TBEs={l2}", f"--DC_TBEs={dc}"]
g["cache_setup"] = cs
g["jobs"] = int(jobs)
cfg["paths"]["results_name"] = name
cfg["pipeline"]["keep_tmp"] = False
hdr = (f"// TBE sweep arm (2026-11-09, cache-random): {src} with --L2_TBEs={l2} --DC_TBEs={dc}, "
       f"cache_setup={cs}, jobs={jobs}, keep_tmp=false. Launcher STAGE3_gem5/triage/cache_setup_20261108/tbe_sweep.sh\n")
open(out, "w").write(hdr + json.dumps(cfg, indent=2) + "\n")
print(f"wrote {out}")
EOF
  log "begin $name"
  python3 testrun.py --once --model STT_6 --config results/$name/run_config.jsonc > results/$name/testrun.log 2>&1
  log "end $name rc=$?"
}
for a in $ARMS; do
  l2=${a%%:*}; dc=${a##*:}
  run "$l2" "$dc" cold &
  run "$l2" "$dc" warm &
done
wait
log "END"
