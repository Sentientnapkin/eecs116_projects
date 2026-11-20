#!/bin/bash
# usage: runarm.sh <arm name> <table tag> <make_arm args...>   (defines via env DEFS)
cd /data/backups/rganapa/Sebastian/eecs116_projects
n=$1; t=$2; shift 2
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
$PY -B research/single_model/learned/make_arm.py l_$n $t "$@" > /dev/null || exit 1
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 $PY -B -m research.single_model.run_variant --name learned_$n --src research/single_model/learned/arms/l_$n.c --defines "$DEFS" --workers 24 > research/single_model/learned/evallogs/$n.log 2>&1
find research/results/single_model/learned_$n -name 'trajectory.mp4' -delete
