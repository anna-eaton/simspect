#!/usr/bin/env bash
# move_campaigns.sh — move some fanout-v2 gem5 campaigns from cafe2 to another node and resume them.
# 2026-11-09, simspect-c8. Run from the Mac. Needs the node set up by scripts/setup_cafe_node.sh.
#   move_campaigns.sh <node> <testset> [jobs]      e.g. move_campaigns.sh cafe3 STT_6_fv2fp 6
# 1. stops that testset's testrun windows on cafe2 (tmux fv2_gem5; the batch in flight is lost, done stems are kept)
# 2. copies to <node>:/tests/simspect_alloy_20261108/: code_20261109 (minus results), the testset's 2% sample
#    stems (asm + ann, both modes; the campaigns sample 1% then 2%, gem5_common.sample_keep), their XMLs,
#    and results_fv2/<row>_<testset>__* (+ __latest)
# 3. runs resume_on_node.sh INSIDE the node's container (stdin; no nested quoting): symlinks, results as a real
#    dir under the code root (testrun --resume needs that), per-node configs with gem5.jobs = [jobs], and one
#    `testrun.py --resume` per campaign in tmux fv2_gem5.
# Every remote command is a plain argument list (ssh joins args and re-parses them, so no bash -lc '...' across a hop).
# Log: ~/Library/Logs/simspect/move_campaigns_<node>_<testset>.log
set -u
NODE=${1:?node}; TS=${2:?testset}; JOBS=${3:-6}
W=/tests/simspect_alloy_20261108
HERE=$(cd "$(dirname "$0")" && pwd)
LOG=~/Library/Logs/simspect/move_campaigns_${NODE}_${TS}.log; mkdir -p "$(dirname "$LOG")"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
step() { log "RUN $1"; shift; "$@" >>"$LOG" 2>&1; rc=$?; log "END rc=$rc"; [ $rc = 0 ] || { log FAILED; exit 1; }; }
C2() { ssh -A -o BatchMode=yes cafe2 "$@"; }

# 1. stop on cafe2 (a list-and-kill script piped into the cafe2 container)
step stop C2 "docker exec -i gem5_dev bash -s" <<EOF
for w in \$(tmux list-windows -t fv2_gem5 -F '#W' | grep '_${TS}\$'); do tmux kill-window -t fv2_gem5:\$w; done
sleep 5; ps -eo pid,args | grep '[t]estrun.py.*--model ${TS} ' || true
EOF
# 2a. file list on cafe2
step list C2 "docker exec -i gem5_dev bash -s" <<EOF
cd $W && python3 - <<'PY'
import sys, glob, os
sys.path.insert(0, "code_20261109/STAGE3_gem5"); from gem5_common import sample_keep
ss = sorted(os.path.basename(x)[:-4] for x in glob.glob("testsets_twostage/STT_6/xml/inst-*.xml") if sample_keep(os.path.basename(x)[:-4], 0.02))
out = ["code_20261109/" + p for p in ("runconfigs", "STAGE2_compilation", "STAGE3_gem5", "specs", "STAGE1_alloy")]
out += sorted(glob.glob("code_20261109/*.py")) + [p for p in ("code_20261109/CODE_SNAPSHOT.txt", "code_20261109/SHA256SUMS") if os.path.exists(p)]
for s in ss:
    out.append(f"testsets_twostage/STT_6/xml/{s}.xml")
    for m in ("mispredict_not_taken", "mispredict_taken"):
        out += [f"testsets_twostage/${TS}/{m}/asm/{s}.s", f"testsets_twostage/${TS}/{m}/ann/{s}.ann.json"]
out += sorted(glob.glob("results_fv2/*_${TS}__*"))
open("move_${TS}.list", "w").write("\n".join(out) + "\n"); print(len(ss), "stems,", len(out), "paths")
PY
EOF
# 2b. stream cafe2 container -> node container (plain argument lists only)
step mkdir C2 "ssh -o BatchMode=yes $NODE docker exec gem5_dev mkdir -p $W/logs"
step copy C2 "docker exec -i gem5_dev tar cf - -C $W -T $W/move_${TS}.list | ssh -o BatchMode=yes $NODE docker exec -i gem5_dev tar xf - -C $W"
# 3. resume inside the node container
step launch ssh -o BatchMode=yes "$NODE" "docker exec -i gem5_dev env TS=$TS JOBS=$JOBS NODE=$NODE bash -s" < "$HERE/resume_on_node.sh"
log "DONE $NODE $TS jobs=$JOBS"
