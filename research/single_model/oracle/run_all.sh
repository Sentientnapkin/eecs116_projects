#!/bin/bash
# runs all oracle arms sequentially (one evaluation at a time)
cd /data/backups/rganapa/Sebastian/eecs116_projects
for a in vx_0.1 vx_0.3 vx_0.6 vx_1.0 vn_0.1 vn_0.3 vn_0.6 vn_1.0 tx_0.02 tn_0.02 tx_0.05 tn_0.05 tx_0.1 tn_0.1 bx_0.1 bx_0.3 bx_0.6 bx_1.0; do
  while [ "$(cut -d. -f1 /proc/loadavg)" -gt 150 ]; do sleep 30; done
  [ -f research/results/single_model/oracle_$a/report.txt ] && continue
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name oracle_$a --src research/single_model/oracle/arms/$a.c --workers 32 > research/results/single_model/oracle_$a.log 2>&1
  find research/results/single_model/oracle_$a -name trajectory.mp4 -delete
done
echo done > research/results/single_model/oracle_alldone
