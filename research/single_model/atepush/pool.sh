#!/bin/bash
# pool.sh NAME CFG "EXTRA" POOL [W] : build ape.c with CFG defs + extras, run pool -> tables/pool_NAME.json
cd /data/backups/rganapa/Sebastian/eecs116_projects
F=research/single_model/atepush; PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python; export OPENBLAS_NUM_THREADS=1
$PY -B -m research.single_model.atepush.mkwasm ape_$1 ${SRC:-$F/ape.c} "$(cat $F/$2.defs) $3" > $F/logs/p_$1.build 2>&1 || { echo BUILDFAIL $1; exit 1; }
$PY -B -m research.single_model.atepush.runpool $1 research/results/single_model/ape_$1/solution.wasm $4 ${5:-20} 2>&1 | tail -1
