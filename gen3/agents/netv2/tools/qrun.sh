#!/bin/bash
# qrun.sh: sequential eval queue. Lines in logs/queue.txt: "NAME WASM POOL..."; processed lines are moved to logs/queue_done.txt
cd /data/backups/rganapa/Sebastian/gen3/agents/netv2
while true; do
  L=$(head -n1 logs/queue.txt 2>/dev/null)
  if [ -z "$L" ]; then sleep 30; continue; fi
  sed -i 1d logs/queue.txt; set -- $L; N=$1; W=$2; shift 2
  tools/evq.sh $N $W "$@"; echo "$(date '+%F %H:%M') $L" >> logs/queue_done.txt
done
