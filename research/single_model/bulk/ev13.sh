#!/bin/bash
# usage: ev13.sh name "defines" [src=b13.c] : 171 (run_variant) + fold-3 unselected + fresh711
cd /data/backups/rganapa/Sebastian/eecs116_projects
N=$1; DEF=$2; SRC=${3:-b13.c}
SRC=${SRC}
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
B=research/single_model/bulk
$PY -B -m research.single_model.run_variant --name $N --src $B/$SRC ${DEF:+--defines "$DEF"} --workers 28 > $B/logs/$N.171.txt 2>&1
W=research/results/single_model/$N/solution.wasm
$PY -B -m research.single_model.bulk.run_f3_bk --name $N --wasm $W --workers 28 > $B/logs/$N.f3.txt 2>&1
$PY -B -m research.single_model.bulk.run_fresh_bk --name $N --wasm $W --workers 28 > $B/logs/$N.fresh.txt 2>&1
