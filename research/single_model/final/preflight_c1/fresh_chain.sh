#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
P=research/single_model/final/preflight_c1
for x in c1:research/results/single_model/preflight_c1_a/solution.wasm g:research/single_model/final/submit/gp_msckf_startup_gate.wasm; do n=${x%%:*}; w=${x#*:}
 mkdir -p /data/backups/rganapa/Sebastian/tmp/pfc1_tmp_$n
 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TMPDIR=/data/backups/rganapa/Sebastian/tmp/pfc1_tmp_$n /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.fresh.run_fresh --name pfc1_$n --wasm "$w" --workers 24 > $P/log_fresh_$n.txt 2>&1
done
