#!/bin/bash
# rp.sh NAME WASM POOLDIR [W] : pool run; log logs/NAME__pool.txt; table tables/NAME__pool.json
cd /data/backups/rganapa/Sebastian/eecs116_projects
export TMPDIR=/data/backups/rganapa/Sebastian/tmp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
/data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.filtcons.runpool "$1" "$(readlink -f $2)" "$3" ${4:-32} > research/single_model/filtcons/logs/$1__$(basename $3).txt 2>&1
tail -1 research/single_model/filtcons/logs/$1__$(basename $3).txt
