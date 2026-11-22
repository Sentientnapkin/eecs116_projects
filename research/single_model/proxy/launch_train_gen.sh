#!/bin/bash
# N detached workers on roster_train.json (startup-student training flights) -> ~/data/lctrain
N=${1:-3}
mkdir -p ~/data/lctrain/logs
cd /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/research/single_model/proxy
for w in $(seq 0 $((N-1))); do
  LP_NUM_THREADS=2 setsid nohup nice -n 5 ~/.venv/bin/python gen_proxy.py generate --roster roster_train.json --raw ~/data/lctrain --worker $w --workers $N > ~/data/lctrain/logs/w$w.log 2>&1 < /dev/null &
done
sleep 3; pgrep -fc "roster_train.json"
