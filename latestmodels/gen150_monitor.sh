#!/bin/bash
# Watchdog for the autonomous 150k regen. Logs progress every 5 min; exits when
# all 3 testsetgens finish (-> notifies the agent) or if errors appear.
cd /tests/simspect
LOG=latestmodels/gen150_monitor.log
PIDS="3752453 3752454 3752455"
while true; do
  alive=0
  for p in $PIDS; do kill -0 $p 2>/dev/null && alive=$((alive+1)); done
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  line="[$ts] gens_alive=$alive load=$(cut -d' ' -f1 /proc/loadavg)"
  for m in STT_6 SPT_6_oneLP Recon_6; do
    xml=$(find testsets_latest/$m/xml -maxdepth 1 -name 'inst-*.xml' -printf . 2>/dev/null | wc -c)
    asm=$(find testsets_latest/$m -path '*/asm/inst-*.s' -printf . 2>/dev/null | wc -c)
    err=$(grep -ho 'errors=[0-9]*' latestmodels/${m}_gen150.log 2>/dev/null | tail -1)
    line="$line | $m xml=$xml asm=$asm $err"
  done
  echo "$line" >> $LOG
  if [ $alive -eq 0 ]; then echo "[$ts] ALL GENS DONE" >> $LOG; break; fi
  sleep 300
done
