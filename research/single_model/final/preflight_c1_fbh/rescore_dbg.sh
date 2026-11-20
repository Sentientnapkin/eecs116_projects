#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
P=research/single_model/final/preflight_c1_fbh
n=$1
mkdir -p /data/backups/rganapa/Sebastian/tmp/pffb_tmp_dbg
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TMPDIR=/data/backups/rganapa/Sebastian/tmp/pffb_tmp_dbg /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name preflight_c1_fbh_dbg --wasm research/results/single_model/preflight_c1_fbh_dbg/solution.wasm --workers 24 > $P/rescore_dbg.log 2>&1
