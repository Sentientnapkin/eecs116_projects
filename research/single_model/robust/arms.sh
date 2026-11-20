#!/bin/bash
# usage: arms.sh name "defines"  (5 replicates on fresh, b6r.c)
cd /data/backups/rganapa/Sebastian/eecs116_projects
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.robust.score_robust research/single_model/robust/b6r.c --name $1 --reps 5 --par 1 --workers 24 --defines "$2" > research/single_model/robust/out/log_$1.txt 2>&1
