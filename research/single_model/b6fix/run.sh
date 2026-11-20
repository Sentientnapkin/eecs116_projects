#!/bin/bash
# usage: run.sh name "defines"  -> selected (171 visible) 3 replicates (r1/r2 are 1% nudges), 2 concurrent then 1
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
one() { OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 $PY -B -m research.single_model.run_variant --name $1 --src research/single_model/b6fix/fx.c --defines "$2" --workers 20 > research/single_model/b6fix/log_$1.txt 2>&1; }
N=$1; D="$2"
one ${N}_r0 "$D" &
one ${N}_r1 "$D PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0" &
wait
one ${N}_r2 "$D PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0"
