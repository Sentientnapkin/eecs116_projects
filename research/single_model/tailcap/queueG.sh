#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/tailcap; B="TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5"
if [ "$1" = a ]; then
$PY -B $L/runset.py pvlive $L/tc_c.c "$B TC_LIVE_TRIG=20" --reps 3 > $L/log_pvlive.txt 2>&1
else
$PY -B $L/runset.py pvw $L/tc_c.c "$B TC_PVW_THR=0.18" --reps 3 > $L/log_pvw.txt 2>&1
fi
