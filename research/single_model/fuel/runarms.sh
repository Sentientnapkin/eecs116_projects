#!/bin/bash
# runarms.sh "<name>|<defines>" ...   (sequential; run two instances in parallel at most)
cd /data/backups/rganapa/Sebastian/eecs116_projects
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
for spec in "$@"; do
  name=${spec%%|*}; defs=${spec#*|}
  /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name fuel_$name --src research/single_model/fuel/v.c --defines "$defs" --workers 24 > research/results/single_model/fuel_$name.log 2>&1
done
