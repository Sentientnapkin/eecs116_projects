#!/bin/bash
# usage: run1.sh name "defines" [src]   builds, runs 171 then fresh 711
cd /data/backups/rganapa/Sebastian/eecs116_projects
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
D=research/single_model/multihyp
SRC=${3:-$D/dbg.c}
$PY -B -m research.single_model.run_variant --name mh_$1 --src $SRC ${2:+--defines "$2"} --workers ${W:-20} > $D/log_$1.txt 2>&1
$PY -B -m research.single_model.fresh.run_fresh --name mh_$1 --wasm research/results/single_model/mh_$1/solution.wasm --workers ${W:-20} > $D/logf_$1.txt 2>&1
