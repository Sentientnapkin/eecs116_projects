#!/bin/bash
# usage: run.sh name "defines"   -> selected-set run lit_<name>_r0 (search+val)
cd /data/backups/rganapa/Sebastian/eecs116_projects
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name lit_$1_r0 --src research/single_model/litfail/lit.c ${2:+--defines "$2"} --workers 24 > research/single_model/litfail/log_$1_r0.txt 2>&1
