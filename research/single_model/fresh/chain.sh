#!/bin/bash
# usage: chain.sh name:wasm name:wasm ...
cd /data/backups/rganapa/Sebastian/eecs116_projects
for x in "$@"; do n=${x%%:*}; w=${x#*:}
 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TMPDIR=/data/backups/rganapa/Sebastian/tmp/fresh_tmp_$n /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.fresh.run_fresh --name $n --wasm "$w" --workers 32 > research/single_model/fresh/log_$n.txt 2>&1
done
