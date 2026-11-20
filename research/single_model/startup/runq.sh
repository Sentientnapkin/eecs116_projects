#!/bin/bash
# usage: runq.sh queuefile ; lines "name|defines" ; uses v3.c ; waits for any other startup_ run first
cd /data/backups/rganapa/Sebastian/eecs116_projects
while IFS='|' read -r name defs; do
  [ -z "$name" ] && continue
  while [ "$(uptime | awk -F'load average: ' '{print $2}' | cut -d. -f1)" -gt 150 ]; do sleep 30; done
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name startup_$name --src research/single_model/startup/${SRC:-v3.c} --defines "$defs" --workers 24 > research/single_model/startup/log_$name.txt 2>&1
  find research/results/single_model/startup_$name/eval -name trajectory.mp4 -delete
done < "$1"
