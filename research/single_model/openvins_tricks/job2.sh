#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/openvins_tricks
export SRC=ob.c
a=$1; d=$2
./run.sh ob_${a}_r0 "$d"
cd /data/backups/rganapa/Sebastian/eecs116_projects
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TMPDIR=/data/backups/rganapa/Sebastian/tmp/fresh_tmp_ob_$a /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.fresh.run_fresh --name ob_$a --wasm research/results/single_model/ob_${a}_r0/solution.wasm --workers 28 > research/single_model/openvins_tricks/log_fresh_ob_$a.txt 2>&1
cd research/single_model/openvins_tricks
case "$d" in *PIXEL_STD*) p1=""; p2="";; *) p1="PIXEL_STD=1.515"; p2="PIXEL_STD=1.485";; esac
./run.sh ob_${a}_r1 "$d $p1 DETECT_MIN_SCORE=1010.0"
./run.sh ob_${a}_r2 "$d $p2 DETECT_MIN_SCORE=990.0"
