#!/bin/bash
# usage: run.sh POOL NAME "DEFS" [NAME "DEFS" ...]  -> build + eval sequentially (20 workers)
cd /data/backups/rganapa/Sebastian/gen3/agents/priors
POOL=$1; shift
while [ $# -gt 1 ]; do
  N=$1; D=$2; shift 2
  [ -f builds/$N/solution.wasm ] || python3 mk.py $N "$D" ${SRC:-gslv_s3.c} || continue
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
  (cd /data/backups/rganapa/Sebastian/gen3 && ../venv-teacher/bin/python -B evalpool.py pr_$N agents/priors/builds/$N/solution.wasm pools/$POOL 20) > logs/${N}__$POOL.log 2>&1
  echo "$N $POOL done $(date +%T)"
done
