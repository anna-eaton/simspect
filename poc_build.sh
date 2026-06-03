#!/bin/bash
set -e
echo "[copy] cp -a /work/stt -> /work/stt-dbg ($(date +%H:%M:%S))"
rm -rf /work/stt-dbg
cp -a /work/stt /work/stt-dbg
echo "[edit] $(date +%H:%M:%S)"
python3 /tests/simspect/poc_edit_lsq.py
echo "[build] scons incremental ($(date +%H:%M:%S))"
cd /work/stt-dbg && scons build/X86/gem5.opt -j 24 2>&1 | tail -25
echo "BUILD_DONE_EXIT_${PIPESTATUS[0]} ($(date +%H:%M:%S))"
