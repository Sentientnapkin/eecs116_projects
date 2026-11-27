#!/bin/bash
# queue runner: pops "NAME SRC DEFS..." lines from queue.txt (edit any time), build + eval v3val (20 workers, waits while load > 170)
cd /data/backups/rganapa/Sebastian/gen3/agents/sweep
[ -n "$1" ] && while kill -0 $1 2>/dev/null; do sleep 20; done
while true; do
  L=$(head -1 queue.txt); [ -z "$L" ] && { sleep 60; continue; }
  sed -i 1d queue.txt
  read N S D <<< "$L"; POOL=v3val; case $N in *_v1) POOL=v1val;; esac
  [ -f builds/$N/solution.wasm ] || python3 mk.py $N "$D" $S >> logs/build.log 2>&1 || { echo "$N BUILD FAIL"; continue; }
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
  for t in 1 2; do
    (cd /data/backups/rganapa/Sebastian/gen3 && ../venv-teacher/bin/python -B evalpool.py sw_$N agents/sweep/builds/$N/solution.wasm agents/sweep/pools/$POOL 20) > logs/${N}__$POOL.log 2>&1 && break
  done
  echo "$N $POOL done $(date +%T) $(sha256sum builds/$N/solution.wasm | cut -c1-8) | $S $D"
done
