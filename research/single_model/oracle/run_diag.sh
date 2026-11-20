#!/bin/bash
# diagnostic velocity arms from make_arms2.py, one evaluation at a time
cd /data/backups/rganapa/Sebastian/eecs116_projects
for a in "$@"; do
  while [ "$(cut -d. -f1 /proc/loadavg)" -gt 150 ] || pgrep -f "run_variant --name oracle_" >/dev/null; do sleep 20; done
  [ -f research/results/single_model/oracle_$a/report.txt ] && continue
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name oracle_$a --src research/single_model/oracle/arms/$a.c --workers 32 > research/results/single_model/oracle_$a.log 2>&1
  find research/results/single_model/oracle_$a -name trajectory.mp4 -delete
done
