#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/lateinit
waitload() { while [ $(cut -d' ' -f1 /proc/loadavg | cut -d. -f1) -gt 170 ]; do sleep 20; done; }
run() { waitload; $PY -B $L/runset.py "$@" > $L/log_$1.txt 2>&1; }
run off $L/li.c "" --sets sel
run gn3 $L/li.c "LI_GATENET=0.3"
run vd1 $L/li.c "LI_VDEC=1"
run vd2 $L/li.c "LI_VDEC=2"
run cf6 $L/li.c "LI_MODE=2 LI_DTH=6"
