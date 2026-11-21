#!/bin/bash
# ev.sh NAME SRC "DEFINES(X=1 Y=2)" [rep=0|1|2] : cmake build + fresh-711 (W workers, default 24); table audit/tables/NAME.json
cd /data/backups/rganapa/Sebastian/eecs116_projects
N=$1; SRC=$2; DEF=$3; REP=${4:-0}
case $REP in 1) DEF="$DEF PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0";; 2) DEF="$DEF PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0";; esac
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
F=research/single_model/audit
while [ $(cut -d. -f1 /proc/loadavg) -gt ${LMAX:-175} ]; do sleep 30; done
$PY -B -m research.single_model.audit.mkwasm aud_$N $F/$SRC "$DEF" > $F/logs/$N.build.txt 2>&1
sha256sum research/results/single_model/aud_$N/solution.wasm >> $F/logs/$N.build.txt
$PY -B -m research.single_model.audit.run_fresh --name $N --wasm research/results/single_model/aud_$N/solution.wasm --workers ${W:-24} > $F/logs/$N.fresh.txt 2>&1
tail -1 $F/logs/$N.fresh.txt
