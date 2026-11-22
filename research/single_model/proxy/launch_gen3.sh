#!/bin/bash
# stop the HSSD-only workers 0 and 3 of roster.json; start 2 workers on roster2.json (ProcTHOR only)
cd /mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/research/single_model/proxy
pkill -f "generate --roster roster.json --raw /home/alexa/data/proxy --worker 0 "
pkill -f "generate --roster roster.json --raw /home/alexa/data/proxy --worker 3 "
for w in 0 1; do
  LP_NUM_THREADS=2 setsid nohup ~/.venv/bin/python gen_proxy.py generate --roster roster2.json --raw ~/data/proxy --worker $w --workers 2 > ~/data/proxy/logs/r2w$w.log 2>&1 < /dev/null &
done
sleep 3; pgrep -fa "gen_proxy.py generate" | cut -c1-140
