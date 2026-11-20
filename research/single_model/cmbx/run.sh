#!/bin/bash
# usage: run.sh name "defines"   (src b8.c)
cd /data/backups/rganapa/Sebastian/eecs116_projects
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name $1 --src research/single_model/cmbx/b8.c ${2:+--defines "$2"} --workers 24 > research/single_model/cmbx/log_$1.txt 2>&1
