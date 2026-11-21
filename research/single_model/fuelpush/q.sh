#!/bin/bash
# q.sh JOBFILE : runs lines "NAME|DEFINES|REP" with 3 concurrent ev.sh (W=32 each); skips names whose table exists
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/fuelpush
while IFS='|' read -r N D R; do
  [ -z "$N" ] && continue; [ -f tables/$N.json ] && continue
  while [ $(pgrep -f "fuelpush.run_fresh" | wc -l) -ge ${QMAX:-3} ]; do sleep 20; done
  LMAX=250 W=32 nohup bash ev.sh $N fp.c "$D" ${R:-0} > logs/$N.ev 2>&1 &
  sleep 60
done < $1
wait
