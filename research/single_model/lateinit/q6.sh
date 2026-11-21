#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/lateinit
waitload() { while [ $(cut -d' ' -f1 /proc/loadavg | cut -d. -f1) -gt 170 ]; do sleep 20; done; }
run() { waitload; flock $L/eval.lock $PY -B $L/runset.py "$@" > $L/log_$1.txt 2>&1; }
run t10 $L/li_frozen2.c "TC_T0=1.0"
run zn3 $L/li_frozen3.c "LI_ZNET=3.0 LI_GATENET=0.3"
run ff30 $L/li_frozen3.c "FAST_FRAMES=30 FAST_MIN_OBS=3"
run p15 $L/li_frozen2.c "TC_PV_THR=0.15"
run gn2 $L/li_frozen3.c "LI_GATENET=0.2"
run ff30m2 $L/li_frozen3.c "FAST_FRAMES=30"
