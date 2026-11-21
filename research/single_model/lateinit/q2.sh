#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/lateinit
while pgrep -f "lateinit/q1.sh" > /dev/null; do sleep 15; done
waitload() { while [ $(cut -d' ' -f1 /proc/loadavg | cut -d. -f1) -gt 170 ]; do sleep 20; done; }
run() { waitload; $PY -B $L/runset.py "$@" > $L/log_$1.txt 2>&1; }
run w1 $L/li_frozen1.c "LI_WIN=1"
