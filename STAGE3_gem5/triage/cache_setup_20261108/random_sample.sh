#!/bin/bash
# cache_setup "random" check (2026-11-09, cache-random session). Run on cafe2 gem5_dev from the tree root
# /tests/simspect_fixed_20261030. Three 590-test campaigns with the FINAL default footprint configs
# (runconfigs/footprint/run_config_STT_6_{cleanupspec,speclfb}_footprint.jsonc, gem5.cache_setup random), changing only
# the testset (paths.testset_dir/model -> a staged stem list), results_name, keep_tmp (true on CleanupSpec, for the UV3
# evidence and classify_uv3_cold.py; false on SpecLFB) and jobs:
#   (1) CleanupSpec, STT_6_rmw, the 590 stems of results/STT_6_rmw_cleanupspec_footprint__20261109_002545 (warm) and
#       STT_6_rmw_cleanupspec_footprint_cold (cold)
#   (2) CleanupSpec, plain STT_6, the same 590 stems (ts of results/STT_6_rmwstems_cleanupspec_footprint_ctrl_cold)
#   (3) SpecLFB, plain STT_6, the first 295 stems per mode of the v2hooks sample
#       (results/STT_6_speclfb_v2hooks__20261107/sample/<mode>.json, seed 20261107)
# Each arm's config is saved as results/<arm>/run_config.jsonc, its log as results/<arm>/testrun.log.
# Usage: random_sample.sh [jobs]      Log: results/cache_random_sample_20261109.log
set -u
cd /tests/simspect_fixed_20261030
JOBS=${1:-8}
L=results/cache_random_sample_20261109.log
log() { echo "$(date +%F_%T) $*" >> "$L"; }
log "START jobs=$JOBS"
# Stage the RMW sample (symlinks to testsets_latest/STT_6_rmw for the warm RMW run's stems) and the SpecLFB sample.
python3 - <<'EOF' >> "$L" 2>&1
import json, os
root = "/tests/simspect_fixed_20261030"
def stage(stems, src, dst):
    for sub, ext in (("asm", ".s"), ("ann", ".ann.json")):
        os.makedirs(os.path.join(dst, sub), exist_ok=True)
        for s in stems:
            p = os.path.join(dst, sub, s + ext)
            if not os.path.lexists(p):
                os.symlink(os.path.join(src, sub, s + ext), p)
    print(f"staged {len(stems)} stems -> {dst}")
for m in ("mispredict_not_taken", "mispredict_taken"):
    warm = f"{root}/results/STT_6_rmw_cleanupspec_footprint__20261109_002545/{m}/ld/window-results.json"
    stems = sorted(r["name"] for r in json.load(open(warm)))
    stage(stems, f"{root}/testsets_latest/STT_6_rmw/{m}",
          f"{root}/results/STT_6_rmw_cleanupspec_footprint_random/ts/STT_6_rmw/{m}")
    smp = json.load(open(f"{root}/results/STT_6_speclfb_v2hooks__20261107/sample/{m}.json"))["stems"][:295]
    stage(sorted(smp), f"{root}/testsets_latest/STT_6/{m}",
          f"{root}/results/STT_6_speclfb_footprint_random_sample/ts/STT_6/{m}")
EOF
run() {  # $1 = base config, $2 = model, $3 = testset_dir, $4 = results name, $5 = keep_tmp (true|false)
  mkdir -p results/$4
  python3 - "$1" "$2" "$3" "$4" "$JOBS" "$5" <<'EOF' >> "$L" 2>&1
import json, re, sys
src, model, ts, name, jobs, keep = sys.argv[1:]
txt = open(src).read()
# strip // comments (none of these configs has // inside a string except URLs, which they do not contain)
cfg = json.loads(re.sub(r"//[^\n]*", "", txt))
assert cfg["gem5"].get("cache_setup") == "random", "base config is not random"
cfg["paths"].update(testset_dir=ts, model=model, results_name=name)
cfg["gem5"]["jobs"] = int(jobs)
cfg["gem5"].pop("sample_fraction", None)
cfg["pipeline"]["keep_tmp"] = keep == "true"
hdr = (f"// cache_setup random check (2026-11-09, cache-random): {src} with paths.testset_dir={ts}, model={model}, "
       f"results_name={name}, jobs={jobs}, keep_tmp={keep}. Launcher STAGE3_gem5/triage/cache_setup_20261108/random_sample.sh\n")
open(f"results/{name}/run_config.jsonc", "w").write(hdr + json.dumps(cfg, indent=2) + "\n")
print(f"wrote results/{name}/run_config.jsonc")
EOF
  log "begin $4"
  python3 testrun.py --once --model "$2" --config results/$4/run_config.jsonc > results/$4/testrun.log 2>&1
  log "end $4 rc=$?"
}
CS=runconfigs/footprint/run_config_STT_6_cleanupspec_footprint.jsonc
LFB=runconfigs/footprint/run_config_STT_6_speclfb_footprint.jsonc
run $CS STT_6_rmw results/STT_6_rmw_cleanupspec_footprint_random/ts STT_6_rmw_cleanupspec_footprint_random true &
run $CS STT_6 results/STT_6_rmwstems_cleanupspec_footprint_ctrl_cold/ts STT_6_rmwstems_cleanupspec_footprint_random true &
run $LFB STT_6 results/STT_6_speclfb_footprint_random_sample/ts STT_6_speclfb_footprint_random_sample false &
wait
log "END"
