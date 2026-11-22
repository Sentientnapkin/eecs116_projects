#!/bin/bash
# qafter.sh PREVJOB JOBFILE [PAR]: wait for logs/q_PREVJOB.txt DONE, then q.sh JOBFILE PAR
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/geomstarve
until grep -q DONE logs/q_$1.txt 2>/dev/null; do sleep 20; done
./q.sh $2 ${3:-2}
