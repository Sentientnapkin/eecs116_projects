#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
R=research/single_model/tailcap/runset.py; S=research/single_model/tailcap/tc_b.c
$PY -B $R rad12 $S "TC_RAD=1 TC_R_OUT=12.0 TC_R_SD=3.0 TC_Z_OUT=6.0" > research/single_model/tailcap/log_rad12.txt 2>&1
$PY -B $R spd25 $S "TC_SPD=1 TC_V3_MAX=2.5 TC_V3_TARGET=1.6 TC_V_SD=0.5" > research/single_model/tailcap/log_spd25.txt 2>&1
$PY -B $R spd20 $S "TC_SPD=1 TC_V3_MAX=2.0 TC_V3_TARGET=1.4 TC_V_SD=0.5" > research/single_model/tailcap/log_spd20.txt 2>&1
$PY -B $R rad22 $S "TC_RAD=1 TC_R_OUT=22.0 TC_Z_OUT=9.0" > research/single_model/tailcap/log_rad22.txt 2>&1
