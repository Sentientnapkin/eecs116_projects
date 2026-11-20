#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
R=research/single_model/tailcap/runset.py; S=research/single_model/tailcap/tc_c.c; L=research/single_model/tailcap
$PY -B $R pv25 $S "TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5" > $L/log_pv25.txt 2>&1
$PY -B $R pv35 $S "TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.35 TC_T0=2.0" > $L/log_pv35.txt 2>&1
$PY -B $R spdk05 $S "LC_SPD_K=0.5" > $L/log_spdk05.txt 2>&1
$PY -B $R spdk10 $S "LC_SPD_K=1.0" > $L/log_spdk10.txt 2>&1
