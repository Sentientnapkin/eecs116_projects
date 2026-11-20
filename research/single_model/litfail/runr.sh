#!/bin/bash
# usage: runr.sh name rep "defines"  -> lit_<name>_r<rep> with chaos nudge for rep 1,2 (same nudges as tails/rep.sh)
cd /data/backups/rganapa/Sebastian/eecs116_projects
case $2 in 1) N="PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0";; 2) N="PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0";; *) N="";; esac
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name lit_$1_r$2 --src research/single_model/litfail/lit.c --defines "$3 $N" --workers 24 > research/single_model/litfail/log_$1_r$2.txt 2>&1
