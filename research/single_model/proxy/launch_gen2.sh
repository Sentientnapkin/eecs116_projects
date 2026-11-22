#!/bin/bash
# launch N detached generator workers (simulator builds already warm); logs in ~/data/proxy/logs
N=${1:-5}
cd /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/research/single_model/proxy
for w in $(seq 0 $((N-1))); do
  LP_NUM_THREADS=2 setsid nohup ~/.venv/bin/python gen_proxy.py generate --roster roster.json --raw ~/data/proxy --worker $w --workers $N > ~/data/proxy/logs/w$w.log 2>&1 < /dev/null &
done
sleep 3
