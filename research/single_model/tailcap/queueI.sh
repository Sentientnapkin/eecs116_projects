#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/tailcap; B="TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5"
while [ ! -f $L/tables/pvlive_r2.json ]; do sleep 10; done
$PY -B $L/runset.py rmf $L/tc_c.c "$B TC_POST=1 TC_ROWMAX=30" --reps 3 > $L/log_rmf.txt 2>&1
