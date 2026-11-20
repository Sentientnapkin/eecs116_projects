#!/bin/bash
# arm.sh name "defines" [fresh]  : 171 sanity (builds be.c) then optionally 711 fresh. results research/results/single_model/fb_<name>
cd /data/backups/rganapa/Sebastian/eecs116_projects
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
n=$1; d=$2; src=${SRC:-be.c}
$PY -B -m research.single_model.run_variant --name fb_$n --src research/single_model/fuelbe/$src --defines "$d" --workers 24 > research/single_model/fuelbe/log_$n.txt 2>&1
if [ "$3" = fresh ]; then
$PY -B -m research.single_model.fuelbe.run_fresh_be --name $n --wasm research/results/single_model/fb_$n/solution.wasm --workers 24 >> research/single_model/fuelbe/log_$n.txt 2>&1
fi
tail -25 research/single_model/fuelbe/log_$n.txt | grep -v "^$" > research/single_model/fuelbe/sum_$n.txt
