#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/tailcap; CM=research/single_model/bulk/exact/CMakeLists.txt
D13="ITER_UPD=2 ITER_BACK=1.0 ITER_TH=0.03 MAP_MODE=1 MAP_AGE=100 MAP_ANG=40 MAP_TRY=6 MAP_ZNCC=0.85 MAP_NEAR=1"
PV="TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5"
if [ "$1" = a ]; then
 while [ ! -f $L/tables/b13_r2.json ]; do sleep 10; done
 $PY -B $L/runset.py b16r $L/tc_e.c "$D13 $PV TC_POST=1 TC_ROWMAX=30" --reps 3 --cmake $CM > $L/log_b16r.txt 2>&1
else
 while [ ! -f $L/tables/b16_r2.json ]; do sleep 10; done
 $PY -B $L/runset.py b16m $L/tc_e.c "$D13 $PV TC_MAPFLUSH=1" --reps 3 --cmake $CM > $L/log_b16m.txt 2>&1
fi
