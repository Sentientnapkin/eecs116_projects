#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/lateinit
waitload() { while [ $(cut -d' ' -f1 /proc/loadavg | cut -d. -f1) -gt 170 ]; do sleep 20; done; }
run() { waitload; flock $L/eval.lock $PY -B $L/runset.py "$@" > $L/log_$1_$$.txt 2>&1; }
run gn2 $L/li_frozen3.c "LI_GATENET=0.2" --reps 2 --first 1
run gnp $L/li_frozen5.c "LI_GATENET=0.2 LI_PVS=1 LI_PVS_T0=3.0" --reps 3
