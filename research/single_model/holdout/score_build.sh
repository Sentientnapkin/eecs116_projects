#!/bin/bash
# usage: score_build.sh <wasm> <name>
# Scores a wasm ONCE on the final holdout set (gen/raw-holdout/final). RULE: each final candidate is scored here at most
# once; results must not be used to tune. Refuses if holdout/table_<name>.json exists. Per-flight table -> holdout/table_<name>.{json,csv};
# raw outputs -> research/results/single_model/holdout_<name>/.
set -e
W=$(readlink -f "$1"); N=$2
[ -f "$W" ] && [ -n "$N" ] || { echo "usage: $0 <wasm> <name>"; exit 2; }
cd /data/backups/rganapa/Sebastian/eecs116_projects
[ ! -e research/single_model/holdout/table_$N.json ] || { echo "holdout rule: $N already scored"; exit 3; }
echo "$(date -u +%FT%TZ) $N $(sha256sum "$W" | cut -c1-16) $W" >> research/single_model/holdout/SCORED.log
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TMPDIR=/data/backups/rganapa/Sebastian/tmp/holdout_tmp_$N mkdir -p /data/backups/rganapa/Sebastian/tmp/holdout_tmp_$N
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TMPDIR=/data/backups/rganapa/Sebastian/tmp/holdout_tmp_$N /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.holdout.run_holdout --name "$N" --wasm "$W" --workers ${WORKERS:-32} 2>&1 | tee research/single_model/holdout/log_$N.txt
