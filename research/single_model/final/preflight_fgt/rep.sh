#!/bin/bash
# usage: rep.sh name src defines -> 3 chaos replicates name_r0..2 (PIXEL_STD / DETECT_MIN_SCORE 1% nudges), as tails/rep.sh
cd /data/backups/rganapa/Sebastian/eecs116_projects
R="env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --src $2 --workers 24"
L=research/single_model/final/preflight_fgt
$R --name ${1}_r0 ${3:+--defines "$3"} > $L/log_${1}_r0.txt 2>&1 &
$R --name ${1}_r1 --defines "$3 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0" > $L/log_${1}_r1.txt 2>&1 &
$R --name ${1}_r2 --defines "$3 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0" > $L/log_${1}_r2.txt 2>&1 &
wait
