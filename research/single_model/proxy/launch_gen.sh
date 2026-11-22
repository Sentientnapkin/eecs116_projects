#!/bin/bash
# warm the simulator builds serially, then launch N detached generator workers; logs in ~/data/proxy/logs
N=${1:-7}
mkdir -p ~/data/proxy/logs
cd /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/research/single_model/proxy
~/.venv/bin/python gen_proxy.py warmup > ~/data/proxy/logs/warmup.log 2>&1 || exit 1
for w in $(seq 0 $((N-1))); do
  LP_NUM_THREADS=2 setsid nohup ~/.venv/bin/python gen_proxy.py generate --roster roster.json --raw ~/data/proxy --worker $w --workers $N > ~/data/proxy/logs/w$w.log 2>&1 < /dev/null &
done
