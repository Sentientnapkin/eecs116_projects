#!/bin/bash
# usage: fresh.sh name  (wasm from results/single_model/<name>/solution.wasm)
cd /data/backups/rganapa/Sebastian/eecs116_projects
n=$1; mkdir -p /data/backups/rganapa/Sebastian/tmp/edge_tmp_$n
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TMPDIR=/data/backups/rganapa/Sebastian/tmp/edge_tmp_$n /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.edge.run_fresh_e --name $n --wasm research/results/single_model/$n/solution.wasm --workers 24 > research/single_model/edge/log_fresh_$n.txt 2>&1
