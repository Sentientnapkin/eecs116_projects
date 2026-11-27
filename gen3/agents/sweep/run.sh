#!/bin/bash
# usage: SRC=file run.sh POOL NAME "DEFS" [NAME "DEFS" ...]  -> build + eval sequentially (20 workers); evals/sw_NAME__POOL.json
cd /data/backups/rganapa/Sebastian/gen3/agents/sweep
POOL=$1; shift
while [ $# -gt 1 ]; do
  N=$1; D=$2; shift 2
  [ -f builds/$N/solution.wasm ] || python3 mk.py $N "$D" ${SRC:-base.c} >> logs/build.log 2>&1 || { echo "$N BUILD FAIL"; continue; }
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
  for t in 1 2; do
    (cd /data/backups/rganapa/Sebastian/gen3 && ../venv-teacher/bin/python -B evalpool.py sw_$N agents/sweep/builds/$N/solution.wasm agents/sweep/pools/$POOL 20) > logs/${N}__$POOL.log 2>&1 && break
  done
  echo "$N $POOL done $(date +%T) $(sha256sum builds/$N/solution.wasm | cut -c1-8)"
done
