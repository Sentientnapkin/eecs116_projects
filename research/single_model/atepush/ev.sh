#!/bin/bash
# ev.sh NAME CFG(B17|T4uB) "EXTRA DEFINES" [rep 0|1|2] [SET fresh|sel] : build atepush/ap.c with CFG defs + extras, run fresh-711; table atepush/tables/NAME.json
cd /data/backups/rganapa/Sebastian/eecs116_projects
N=$1; CFG=$2; X=$3; REP=${4:-0}
F=research/single_model/atepush
DEF="$(cat $F/$CFG.defs) $X"
case $REP in 1) DEF="$DEF PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0";; 2) DEF="$DEF PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0";; esac
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
while [ $(cut -d. -f1 /proc/loadavg) -gt ${LMAX:-170} ]; do sleep 30; done
$PY -B -m research.single_model.atepush.mkwasm ap_$N ${SRC:-$F/ape.c} "$DEF" > $F/logs/$N.build.txt 2>&1 || { echo BUILD FAIL $N; exit 1; }
$PY -B -m research.single_model.atepush.run_fresh --name $N --wasm research/results/single_model/ap_$N/solution.wasm --workers ${W:-32} > $F/logs/$N.fresh.txt 2>&1
tail -1 $F/logs/$N.fresh.txt
