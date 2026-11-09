#!/bin/bash
# runall_stt.sh (STT agent 2026-11-09): the full STT_6_u verification queue, in priority order; each
# runbatch_stt.sh call takes the shared lock once (mkdir) and releases it on exit.
cd "$(dirname "$0")"
./runbatch_stt.sh 600 5000 q_fast.als
./runbatch_stt.sh 240 5000 q_stl.als q_stl_gen.als q_core_u_core.als q_core_u_stl_core.als q_asm_sk.als q_asm_stl_sk.als
./runbatch_stt.sh 900 5000 q_gen.als
./runbatch_stt.sh 600 5000 q_yrot.als
./runbatch_stt.sh 240 5000 q_sem2_gen.als
./rundump_stt.sh 240 30 q_dump.als q_dump_stl.als
echo "QUEUE DONE $(date +%T)" >> runs.log
