#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
P=research/single_model/final/preflight_c1_fbh
mkdir -p /data/backups/rganapa/Sebastian/tmp/pffb_tmp_fresh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TMPDIR=/data/backups/rganapa/Sebastian/tmp/pffb_tmp_fresh /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.fresh.run_fresh --name pfbh_fresh --wasm research/results/single_model/preflight_c1_fbh_a/solution.wasm --workers 24 > $P/log_fresh.txt 2>&1
echo done > $P/fresh.done
