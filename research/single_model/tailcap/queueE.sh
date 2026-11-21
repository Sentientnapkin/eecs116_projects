#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/tailcap
for p in 0 1 2 3; do
$PY -B $L/runset.py phb$p $L/tc_c.c "TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5 TC_PHB=$p" --sets sel > $L/log_phb$p.txt 2>&1
done
