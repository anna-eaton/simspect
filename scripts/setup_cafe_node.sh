#!/usr/bin/env bash
# setup_cafe_node.sh — clone cafe2's gem5_dev container setup onto another cafe node (cafe1, cafe3).
#
# 2026-11-09, simspect-c8 (Anna: "try the other two, but set up docker the same as cafe2").
# Run from the Mac. Needs: a Slurm holder job on the target node (pam_slurm_adopt), the Mac's ssh
# agent (keys loaded; we use `ssh -A cafe2` so cafe2 can reach the node with the forwarded key, no
# key is stored on the cluster), and the snapshot image already committed on cafe2:
#   ssh cafe2 "docker commit --pause=false gem5_dev simspect_gem5_dev:20261109"
# Data never passes through the Mac: every stream runs cafe2 -> node.
#
# What it makes on <node> (same as cafe2): image $IMG; volumes gem5_tests (/tests), gem5_work (/work),
# gem5_base (/opt/gem5-base); container gem5_dev = `docker run -d --name gem5_dev <the 3 mounts> $IMG
# sleep infinity` (cafe2's container: bridge network, no cpu/mem limits, cmd sleep infinity).
# /work gets only the gem5 trees the eval rows use (WORK_DIRS), at the same absolute paths.
# /tests starts empty; workloads copy their own workspace in.
#
# Usage: scripts/setup_cafe_node.sh <node> [step...]   steps: image volumes base work container check (default: all)
# Log: ~/Library/Logs/simspect/setup_cafe_node_<node>.log (every step, with timestamps and exit codes).
set -u
NODE=${1:?usage: setup_cafe_node.sh <node> [steps]}; shift
STEPS=${*:-image volumes base work container check}
IMG=${IMG:-simspect_gem5_dev:20261109}
WORK_DIRS=${WORK_DIRS:-"gem5-recon-modded stt-master stt amulet/amulet-gem5-STT_AE-v1.1 amulet/amulet-gem5-InvisiSpec_AE-v1.1 amulet/amulet-gem5-CleanupSpec_AE-v1.1 amulet/amulet-gem5-SpecLFB_AE-v1.1"}
LOG=~/Library/Logs/simspect/setup_cafe_node_${NODE}.log
mkdir -p "$(dirname "$LOG")"
log() { echo "$(date -u +%FT%TZ) [$NODE] $*" | tee -a "$LOG"; }
run() { log "RUN $1"; ssh -A -o BatchMode=yes cafe2 "$2" >>"$LOG" 2>&1; rc=$?; log "END $1 rc=$rc"; return $rc; }
R="ssh -o BatchMode=yes $NODE"

for s in $STEPS; do case $s in
  image)     run image "docker image inspect $IMG >/dev/null && docker save $IMG | $R 'docker load'" ;;
  volumes)   run volumes "$R 'for v in gem5_tests gem5_work gem5_base; do docker volume create \$v; done'" ;;
  base)      run base "docker exec gem5_dev tar cf - -C /opt/gem5-base . | $R 'docker run -i --rm -v gem5_base:/dst $IMG tar xf - -C /dst'" ;;
  work)      run work "docker exec gem5_dev tar cf - -C /work $WORK_DIRS | $R 'docker run -i --rm -v gem5_work:/work $IMG tar xf - -C /work'" ;;
  container) run container "$R 'docker ps -a --format {{.Names}} | grep -qx gem5_dev || docker run -d --name gem5_dev -v gem5_tests:/tests -v gem5_work:/work -v gem5_base:/opt/gem5-base $IMG sleep infinity'" ;;
  check)     run check "$R 'docker exec gem5_dev bash -lc \"nproc; java -version 2>&1 | head -1; which clang python3; du -sh /work/* /opt/gem5-base 2>/dev/null; ls /work/gem5-recon-modded/build/X86/gem5.opt /work/stt-master/build/X86/gem5.opt\"'" ;;
  *) log "unknown step $s"; exit 2 ;;
esac || { log "FAILED at step $s"; exit 1; }; done
log "DONE steps: $STEPS"
