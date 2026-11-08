#!/bin/bash
# Scratch build of a SpecLFB gem5 tree for the jmp-shadow investigation. Never touches the live tree.
# usage: build.sh <tree_dir> <tag> ; log -> /work/amulet/jmpshadow_probe/build_<tag>.log
set -u
T=$1; tag=$2; J=${J:-16}
LOG=/work/amulet/jmpshadow_probe/build_${tag}.log
cd $T || exit 1
echo "[$(date -Iseconds)] START tree=$T tag=$tag j=$J" >> $LOG
SCONS_LIB_DIR= python3 /usr/bin/scons -j$J build/X86/gem5.opt --ignore-style </dev/null >> $LOG 2>&1
rc=$?
echo "[$(date -Iseconds)] END tag=$tag rc=$rc" >> $LOG
echo "- $(date -u +%FT%TZ) build $tag rc=$rc (log build_${tag}.log)" >> /work/amulet/jmpshadow_probe/LOG.md
exit $rc
