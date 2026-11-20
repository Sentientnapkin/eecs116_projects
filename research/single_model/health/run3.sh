#!/bin/bash
# usage: run.sh name "DEFINES"
cd /data/backups/rganapa/Sebastian/eecs116_projects
while [ $(uptime | sed 's/.*average: \([0-9]*\).*/\1/') -gt 150 ]; do sleep 20; done
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant --name health_$1 --src research/single_model/health/hv3.c --defines "$2" --workers 32 2>&1 | tail -12
find research/results/single_model/health_$1/eval -name trajectory.mp4 -delete
