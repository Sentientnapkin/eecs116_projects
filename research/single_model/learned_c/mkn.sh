#!/bin/bash
# mkn.sh NAME RUN [SCALE]: export run -> w_NAME, build lc_NAME.c (B7-exact base, core2, single net, scale)
cd /data/backups/rganapa/Sebastian/eecs116_projects
export PYTHONPATH=.:/dev/shm/sebastian-vio/viobench OPENBLAS_NUM_THREADS=1
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python; L=research/single_model/learned_c
mkdir -p $L/w_$1; $PY -B $L/export_multi.py $L/w_$1/lc_weights.h $L/runs/$2 > /dev/null
LC_CORE=lc_core2.h LC_BASE=research/single_model/fuel/adopted_c1_fbh_exact.c $PY -B $L/make_lc.py $L/lc_$1.c $L/w_$1 LC_SCALE=${3:-1.0} LC_OFF_C0=1 > /dev/null
