#!/usr/bin/env bash
# Queued, DEPRIORITIZED recon run — waits until the priority sweeps (A/B/D)
# drain and the box has headroom, then resumes the Recon_6 regen + watcher
# behind them. Recon = STT scheme 2 + --allow_leaked (results/Recon_6 config).
# Launch:  nohup ./queue_recon_behind.sh > queue_recon_behind.log 2>&1 &
set -u
cd /tests/simspect
THRESH=35          # 1-min load must drop below this (priority sweeps idle/done)
NEED=2             # consecutive sub-threshold checks before we go
INTERVAL=300       # poll cadence (s)
ok=0
echo "[queue] $(date '+%F %T') waiting for load < $THRESH (x$NEED) before recon"
while true; do
  load1=$(awk '{print int($1)}' /proc/loadavg)
  if [ "$load1" -lt "$THRESH" ]; then
    ok=$((ok+1)); echo "[queue] $(date '+%F %T') load=$load1 < $THRESH  ($ok/$NEED)"
    [ "$ok" -ge "$NEED" ] && break
  else
    ok=0; echo "[queue] $(date '+%F %T') load=$load1 >= $THRESH  (waiting)"
  fi
  sleep "$INTERVAL"
done

echo "[queue] $(date '+%F %T') headroom reached — launching recon (nice 19)"
# Producer: resume asm regen (skips the ~30k already built). nice'd so even if
# it overlaps a tail of the priority runs it yields to them.
nice -n 19 python3 -u pipeline.py asm --model Recon_6 \
     --config results/Recon_6/run_config.jsonc \
     >> pipeline_Recon_6_regen.log 2>&1 &
echo "[queue] recon asm-resume pid=$!"
# Consumer: resume the existing campaign (results/Recon_6__latest), type-sorted.
nice -n 19 python3 -u testrun.py --config results/Recon_6/run_config.jsonc \
     --model Recon_6 --interval 300 --max-new 1500 --resume \
     >> results/Recon_6_allowleaked_watcher.log 2>&1 &
echo "[queue] recon watcher pid=$!"
echo "[queue] $(date '+%F %T') recon launched behind priority runs."
