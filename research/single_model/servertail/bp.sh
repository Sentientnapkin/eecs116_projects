#!/bin/bash
# bp.sh NAME SRC "DEFS" POOL1 [POOL2 ...] : build (servertail/CMakeLists) + run on pools sequentially (W env, default 32)
cd /data/backups/rganapa/Sebastian/eecs116_projects
export TMPDIR=/data/backups/rganapa/Sebastian/tmp
N=$1; SRC=$2; DEF=$3; shift 3
F=research/single_model/servertail; mkdir -p $F/logs
/data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.servertail.mkwasm st_$N $F/$SRC "$DEF" > $F/logs/$N.build.txt 2>&1 || { echo BUILD FAIL $N; exit 1; }
sha256sum research/results/single_model/st_$N/solution.wasm >> $F/logs/$N.build.txt
for P in "$@"; do bash $F/rp.sh $N research/results/single_model/st_$N/solution.wasm $P ${W:-32}; done
