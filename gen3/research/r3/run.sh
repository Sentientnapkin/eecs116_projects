#!/bin/bash
# run.sh POOL NAME [NAME...] : eval research/r3/builds/NAME as r3 eval NAME (names already r3_-prefixed) on gen3/pools/POOL, 8 workers, load wait
cd /data/backups/rganapa/Sebastian/gen3
POOL=$1; shift
for N in "$@"; do
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 30; done
  ../venv-teacher/bin/python -B evalpool.py $N research/r3/builds/$N/solution.wasm pools/$POOL 8 > research/r3/logs/${N}__$POOL.log 2>&1
  echo "$N $POOL done $(date +%T)" >> research/r3/logs/queue.log
done
