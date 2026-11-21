#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
L=research/single_model/tailcap; CM=research/single_model/bulk/exact/CMakeLists.txt
D13="ITER_UPD=2 ITER_BACK=1.0 ITER_TH=0.03 MAP_MODE=1 MAP_AGE=100 MAP_ANG=40 MAP_TRY=6 MAP_ZNCC=0.85 MAP_NEAR=1"
PV="TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5"
case $1 in
 off) $PY -B $L/runset.py b13off $L/tc_d.c "$D13" --sets sel --cmake $CM > $L/log_b13off.txt 2>&1 ;;
 base) $PY -B $L/runset.py b13 $L/tc_b13.c "$D13" --reps 3 --cmake $CM > $L/log_b13.txt 2>&1 ;;
 pv) $PY -B $L/runset.py b16 $L/tc_d.c "$D13 $PV" --reps 3 --cmake $CM > $L/log_b16.txt 2>&1 ;;
 rm) $PY -B $L/runset.py b16r $L/tc_d.c "$D13 $PV TC_POST=1 TC_ROWMAX=30" --reps 3 --cmake $CM > $L/log_b16r.txt 2>&1 ;;
esac
