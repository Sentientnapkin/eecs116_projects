#!/bin/bash
# usage: run_batch.sh "name|defines" ...   (sequential; waits for low load)
cd /data/backups/rganapa/Sebastian/eecs116_projects
for spec in "$@"; do
  name="${spec%%|*}"; defs="${spec#*|}"
  while [ "$(cut -d' ' -f1 /proc/loadavg | cut -d. -f1)" -gt 150 ]; do sleep 20; done
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name "$name" --src research/single_model/texture/texture.c --defines "$defs" --workers 32 > research/single_model/texture/logs_$name.txt 2>&1
  find research/results/single_model/$name/eval -name trajectory.mp4 -delete
done
