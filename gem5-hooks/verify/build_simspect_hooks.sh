#!/bin/bash
# SimSpect hooks rebuild (2026-10-28). Usage: build_simspect_hooks.sh <InvisiSpec|CleanupSpec|SpecLFB>
set -u
b=$1
LOG=/work/amulet/rebuild_${b}_simspect_hooks_20261028.log
cd /work/amulet/amulet-gem5-${b}_AE-v1.1 || exit 1
echo "[$(date -Iseconds)] START $b" >> $LOG
if [ $b = SpecLFB ]; then
  SCONS_LIB_DIR= python3 /usr/bin/scons -j12 build/X86/gem5.opt --ignore-style </dev/null >> $LOG 2>&1
else
  SCONS_LIB_DIR=/usr/local/lib/python2.7/dist-packages/scons-2.5.1 python2 /usr/local/bin/scons -j12 build/X86_MESI_Two_Level/gem5.opt </dev/null >> $LOG 2>&1
fi
rc=$?
echo "[$(date -Iseconds)] END $b rc=$rc" >> $LOG
