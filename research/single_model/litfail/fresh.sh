#!/bin/bash
# usage: fresh.sh name  -> fresh 711 on lit_<name>_r0 wasm
cd /data/backups/rganapa/Sebastian/eecs116_projects
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.fresh.run_fresh --name lit_$1 --wasm research/results/single_model/lit_$1_r0/solution.wasm --workers 24 > research/single_model/litfail/log_fresh_$1.txt 2>&1
