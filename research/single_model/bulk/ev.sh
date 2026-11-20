#!/bin/bash
# usage: ev.sh name "defines" [src=b6bulk.c] [skip171=0]  -> 171 sanity (run_variant) then fresh 711 (run_fresh_bk)
cd /data/backups/rganapa/Sebastian/eecs116_projects
N=$1; DEF=$2; SRC=${3:-b6bulk.c}
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
$PY -B -m research.single_model.run_variant --name $N --src research/single_model/bulk/$SRC ${DEF:+--defines "$DEF"} --workers 24 > research/single_model/bulk/logs/$N.171.txt 2>&1
$PY -B -m research.single_model.bulk.run_fresh_bk --name $N --wasm research/results/single_model/$N/solution.wasm --workers 28 > research/single_model/bulk/logs/$N.fresh.txt 2>&1
