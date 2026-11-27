#!/bin/bash
# run.sh POOL NAME... : eval research/r2/builds/NAME/solution.wasm on gen3/pools/POOL -> gen3/evals/r2_NAME__POOL.json (8 workers, load wait)
cd /data/backups/rganapa/Sebastian/gen3
POOL=$1; shift
for n in "$@"; do
  while [ "$(cut -d. -f1 /proc/loadavg)" -gt 170 ]; do sleep 60; done
  ../venv-teacher/bin/python -B evalpool.py r2_$n research/r2/builds/$n/solution.wasm pools/$POOL 8 > research/r2/logs/r2_${n}__$POOL.log 2>&1
  tail -5 research/r2/logs/r2_${n}__$POOL.log | head -1
done
