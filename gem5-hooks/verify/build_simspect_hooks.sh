#!/bin/bash
# SimSpect hooks rebuild (v1 2026-10-28, v2 2026-10-30).
# Usage: build_simspect_hooks.sh <InvisiSpec|CleanupSpec|SpecLFB> [tag]
#   tag defaults to v2_20261030 -> log /work/amulet/rebuild_<build>_simspect_hooks_<tag>.log
#   J=<jobs> overrides the scons -j (default 24).
# Doc: wiki/design/SIMSPECT_HOOKS.md ("How to verify", "Backups").
set -u
b=$1
tag=${2:-v2_20261030}
J=${J:-24}
LOG=/work/amulet/rebuild_${b}_simspect_hooks_${tag}.log
cd /work/amulet/amulet-gem5-${b}_AE-v1.1 || exit 1
echo "[$(date -Iseconds)] START $b tag=$tag j=$J" >> $LOG
if [ $b = SpecLFB ]; then
  SCONS_LIB_DIR= python3 /usr/bin/scons -j$J build/X86/gem5.opt --ignore-style </dev/null >> $LOG 2>&1
else
  SCONS_LIB_DIR=/usr/local/lib/python2.7/dist-packages/scons-2.5.1 python2 /usr/local/bin/scons -j$J build/X86_MESI_Two_Level/gem5.opt </dev/null >> $LOG 2>&1
fi
rc=$?
echo "[$(date -Iseconds)] END $b rc=$rc" >> $LOG
exit $rc
