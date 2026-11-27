#!/bin/bash
# queue runner: pops "NAME POOL DEFS..." from queue.txt; Z flags are prepended; SRC env/default base.c. evals/an_NAME__POOL.json, 14 workers
cd /data/backups/rganapa/Sebastian/gen3/agents/anchors
Z="PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0"
while true; do
  L=$(head -1 queue.txt); [ -z "$L" ] && { sleep 30; continue; }
  sed -i 1d queue.txt
  read N POOL D <<< "$L"; S=base.c; case "$D" in SRC:*) S=${D%% *}; S=${S#SRC:}; D=${D#* };; esac
  [ -f builds/$N/solution.wasm ] || python3 mk.py $N "$Z $D" $S >> logs/build.log 2>&1 || { echo "$N BUILD FAIL" >> logs/done.txt; continue; }
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
  for t in 1 2; do
    (cd /data/backups/rganapa/Sebastian/gen3 && ../venv-teacher/bin/python -B evalpool.py an_$N agents/anchors/builds/$N/solution.wasm agents/anchors/pools/$POOL 14) > logs/${N}__$POOL.log 2>&1 && break
  done
  echo "$N $POOL $(date +%T) $(sha256sum builds/$N/solution.wasm | cut -c1-8) | $D" >> logs/done.txt
done
