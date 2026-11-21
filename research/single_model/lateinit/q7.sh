#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/lateinit
waitload() { while [ $(cut -d' ' -f1 /proc/loadavg | cut -d. -f1) -gt 170 ]; do sleep 20; done; }
run() { waitload; flock $L/eval.lock $PY -B $L/runset.py "$@" > $L/log_$1.txt 2>&1; }
sleep 60
run pvs3 $L/li_frozen4.c "LI_PVS=1 LI_PVS_T0=3.0"
run pvs1 $L/li_frozen4.c "LI_PVS=1 LI_PVS_T0=1.5"
