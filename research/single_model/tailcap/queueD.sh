#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/tailcap; S=$L/tc_c.c
if [ "$1" = a ]; then
$PY -B $L/runset.py pull $S "TC_PULL=1 TC_PULL_SD=2.0" > $L/log_pull.txt 2>&1
$PY -B $L/runset.py base $L/tc_base.c "" --first 1 --reps 2 > $L/log_base12.txt 2>&1
else
$PY -B $L/runset.py pv25 $S "TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5" --first 1 --reps 2 > $L/log_pv25_12.txt 2>&1
fi
