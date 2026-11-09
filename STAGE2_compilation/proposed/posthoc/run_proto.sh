#!/bin/bash
# run_proto.sh <workdir>: graph-checker prototype measurements (wiki/design/POSTHOC_GRAPH_CHECKER.md "Prototype").
# Expects <workdir>/{bulk_stt,bulk_spt,exprs_*.txt} from graph_xml.py (see the doc for the generation snippet).
# Waits until no other Alloy java runs (one java at a time on the Mac), then runs PosthocEval sequentially.
set -u
H=$(cd "$(dirname "$0")" && pwd); W=$1
M=$H/../../../STAGE1_alloy/models; J=/opt/homebrew/opt/openjdk@17/bin/java; CP=$H/../../../STAGE1_alloy/alloy6.jar:$H
while pgrep -f "java.*alloy6" >/dev/null; do sleep 15; done
echo "start $(date '+%F %T')"
$J -Xmx1g -cp $CP PosthocEval $M/STT_6.als $W/exprs_stt_9.txt $W/inst-0000*.xml > $W/run1.txt 2>&1
$J -Xmx1g -cp $CP PosthocEval $M/STT_6.als $W/exprs_stt_bulk.txt $W/bulk_stt/*.xml > $W/run_stt.txt 2>&1
$J -Xmx1g -cp $CP PosthocEval $M/proposed/STT_6_v2.als $W/exprs_sttv2_bulk.txt $W/bulk_stt/*.xml > $W/run_sttv2.txt 2>&1
$J -Xmx1g -cp $CP PosthocEval $M/SPT_6_oneLP_v2.als $W/exprs_spt_9.txt $W/bulk_spt/*.xml > $W/run_spt.txt 2>&1
$J -Xmx1g -cp $CP PosthocEval $M/STT_6.als $W/exprs_stt_bulk.txt $H/../../../results/model_fixes_20261108/sample_STT_6.out/inst-*.xml > $W/run_stt3000.txt 2>&1
echo "end $(date '+%F %T')"
