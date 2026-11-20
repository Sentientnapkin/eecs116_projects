#!/bin/bash
# usage: arm.sh name "defines" : builds+selected r0 then fresh 711 -> table_<name>.json
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
N=$1
[ -f research/results/single_model/${N}_r0/solution.wasm ] || $PY -B -m research.single_model.run_variant --name ${N}_r0 --src research/single_model/b6fix/fx.c --defines "$2" --workers 24 > research/single_model/b6fix/log_${N}_r0.txt 2>&1
$PY -B -m research.single_model.fresh.run_fresh --name $N --wasm research/results/single_model/${N}_r0/solution.wasm --workers 24 > research/single_model/b6fix/log_fresh_$N.txt 2>&1
