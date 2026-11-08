#!/bin/bash
# jmp-shadow probe runner. Builds the natural-mispredict gadget for each SHADOW
# variant and runs it on a given gem5.opt with native SpecLFB prints as the oracle.
# usage: run.sh <gem5.opt> <se.py> <outdir-tag> [secret]
# No SimSpect flags: no --branch-ann-file, no stall hooks. Natural mispredict only.
set -u
GEM5=$1; SE=$2; TAG=$3; SECRET=${4:-5}
BASE=/work/amulet/jmpshadow_probe
OUT=$BASE/runs/$TAG
mkdir -p $OUT
SRC=$BASE/src
LOG=$BASE/LOG.md
echo "- $(date -u +%FT%TZ) run.sh TAG=$TAG gem5=$GEM5 secret=$SECRET" >> $LOG
for S in 0 1 2 3 4 5 6 7 8 9 10; do
  D=$OUT/s$S
  mkdir -p $D
  gcc -O2 -no-pie -static -DSHADOW=$S -o $D/g $SRC/driver.c $SRC/gadget.S 2>$D/cc.log
  if [ ! -x $D/g ]; then echo "SHADOW=$S build FAIL (see $D/cc.log)"; continue; fi
  $GEM5 --outdir=$D \
    --debug-flags=Speclfb,Cache,O3PipeView --debug-file=trace.txt \
    $SE --cmd=$D/g --options="$SECRET" \
    --cpu-type=DerivO3CPU --caches --scheme=Speclfb --l2cache \
    --l1d_size=1kB --l1d_assoc=2 --l1i_size=32kB --l1i_assoc=8 \
    --l2_size=2MB --l2_assoc=16 > $D/stdout 2>$D/stderr
  echo "SHADOW=$S rc=$? $(grep -c 'JMPSHADOW secret' $D/stdout) lines"
done
