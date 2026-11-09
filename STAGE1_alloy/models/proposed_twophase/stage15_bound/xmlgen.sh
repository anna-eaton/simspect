#!/bin/bash
# xmlgen.sh — enumerate a few seeded Stage-1.5 models to XML (production driver a6CountModels) so Stage 2
# can be checked at larger bounds. stage15-bound session 2026-11-08. Run from the workspace root (<ws>).
# Usage: bash STAGE1_alloy/models/proposed_twophase/stage15_bound/xmlgen.sh <ws> [limit]
set -x
WS=$1; LIMIT=${2:-100}
H=STAGE1_alloy/models/proposed_twophase/stage15_bound
cd "$WS"
for spec in "STT_6 STT_6__k3_inst-000005.txt 6 a 0" "STT_6 STT_6__k3_inst-000005.txt 10 b 20" \
            "STT_6 STT_6__k3_inst-000005.txt 12 b 24" "SPT_6_oneLP_v2 SPT_6_oneLP_v2__k3_inst-000030.txt 10 b 20"; do
  set -- $spec
  name=${1}_n${3}_pin${4}
  ops=""; [ "$5" != 0 ] && ops="--operands $5"
  python3 $H/make_s15_model.py --model STAGE1_alloy/models/$1.als --core $H/cores/$2 --n $3 --pin $4 $ops --out xmlgen/$name.als
  mkdir -p xmlgen/$name/xml
  date; ( cd STAGE1_alloy && timeout 1500 java -Xmx16g -cp alloy6.jar:$WS/$H a6CountModels ../xmlgen/$name.als ../xmlgen/$name/xml $LIMIT > ../xmlgen/$name.java.log 2>&1 ); echo "$name rc=$? n=$(ls xmlgen/$name/xml/*.xml | wc -l)"; date
done
