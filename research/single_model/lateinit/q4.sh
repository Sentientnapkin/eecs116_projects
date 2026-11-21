#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/lateinit
while pgrep -f "q1.sh" > /dev/null; do sleep 15; done
sleep 30
waitload() { while [ $(cut -d' ' -f1 /proc/loadavg | cut -d. -f1) -gt 170 ]; do sleep 20; done; }
run() { waitload; flock $L/eval.lock $PY -B $L/runset.py "$@" > $L/log_$1.txt 2>&1; }
run zn3 $L/li_frozen3.c "LI_ZNET=3.0 LI_GATENET=0.3"
run gn2 $L/li_frozen3.c "LI_GATENET=0.2"
