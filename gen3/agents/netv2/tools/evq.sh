#!/bin/bash
# evq.sh NAME WASM [pools...] : sequential evals (14 workers, waits for load <= 170) -> gen3/evals/nv2_NAME__POOL.json
N=$1; W=$2; shift 2
for p in ${@:-v3val}; do /data/backups/rganapa/Sebastian/gen3/agents/netv2/tools/ev.sh nv2_$N $W $p 14 > /data/backups/rganapa/Sebastian/gen3/agents/netv2/logs/ev_${N}_$p.log 2>&1; done
