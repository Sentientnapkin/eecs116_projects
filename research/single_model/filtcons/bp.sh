#!/bin/bash
# bp.sh NAME SRC "DEFS" POOL1 [POOL2 ...] : build (fc_NAME) + run pools. NAME ending _r1/_r2 adds the rep perturbation defines.
cd /data/backups/rganapa/Sebastian/eecs116_projects
export TMPDIR=/data/backups/rganapa/Sebastian/tmp
N=$1; SRC=$2; DEF=$3; shift 3
case $N in *_r1) DEF="$DEF PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0";; *_r2) DEF="$DEF PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0";; esac
F=research/single_model/filtcons
/data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.filtcons.mkwasm fc_$N $F/$SRC "$DEF" > $F/logs/$N.build.txt 2>&1 || { echo BUILD FAIL $N; exit 1; }
sha256sum research/results/single_model/fc_$N/solution.wasm >> $F/logs/$N.build.txt
for P in "$@"; do bash $F/rp.sh $N research/results/single_model/fc_$N/solution.wasm $P ${W:-32}; done
