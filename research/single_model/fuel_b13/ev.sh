#!/bin/bash
# ev.sh NAME SRC "DEFINES" [rep=0|1|2] : build + fresh-711 (24 workers). rep1/2 add the matched nudges (PIXEL_STD, DETECT_MIN_SCORE) as in bulk.
cd /data/backups/rganapa/Sebastian/eecs116_projects
N=$1; SRC=$2; DEF=$3; REP=${4:-0}
case $REP in 1) DEF="$DEF PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0";; 2) DEF="$DEF PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0";; esac
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
F=research/single_model/fuel_b13
LD=$(cut -d' ' -f1 /proc/loadavg); echo "load $LD"
$PY -B -m research.single_model.fuel_b13.mkwasm fb_$N $F/$SRC "$(sed 's/-D//g' $F/defs.txt) $DEF" > $F/logs/$N.build.txt 2>&1
$PY -B -m research.single_model.fuel_b13.run_fresh_fb --name $N --wasm research/results/single_model/fb_$N/solution.wasm --workers ${W:-24} > $F/logs/$N.fresh.txt 2>&1
tail -1 $F/logs/$N.fresh.txt
