#!/bin/bash
# ev.sh NAME WASM [pools...] : sequential evals, 14 workers, waits while load > 170 -> gen3/evals/sn_NAME__POOL.json
N=$1; W=$2; shift 2
cd /data/backups/rganapa/Sebastian/gen3
for p in ${@:-v3val}; do
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
  ../venv-teacher/bin/python -B evalpool.py sn_$N $W pools/$p 14 > agents/smallnet/logs/ev_${N}_$p.log 2>&1
done
