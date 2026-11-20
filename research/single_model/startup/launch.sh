#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/startup
for q in qa qb qc; do setsid nohup ./runq.sh $PWD/$q.txt > run_$q.out 2>&1 < /dev/null & sleep 3; done
