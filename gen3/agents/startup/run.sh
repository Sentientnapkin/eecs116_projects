#!/bin/bash
# run.sh POOL NAME [NAME...] : eval builds/NAME as st_NAME on gen3/pools/POOL (14 workers, waits while load > 170)
cd /data/backups/rganapa/Sebastian/gen3
POOL=$1; shift
for N in "$@"; do
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 30; done
  ../venv-teacher/bin/python -B evalpool.py st_$N agents/startup/builds/$N/solution.wasm pools/$POOL 14 > agents/startup/logs/${N}__$POOL.log 2>&1
  echo "$N $POOL done $(date +%T)"
done
