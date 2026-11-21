#!/bin/bash
# qe.sh NAME SRC "DEFS" : quick 48-flight fresh subset eval (16 workers) -> tables/q_NAME.json
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
F=research/single_model/tier1m
$PY -B -m research.single_model.tier1m.mkwasm t1q_$1 $F/$2 "$3" > $F/logs/q_$1.build.txt 2>&1 || { cat $F/logs/q_$1.build.txt | tail -5; exit 1; }
$PY -B -m research.single_model.tier1m.run_q --name $1 --wasm research/results/single_model/t1q_$1/solution.wasm --workers ${W:-16} 2>&1 | tail -1
