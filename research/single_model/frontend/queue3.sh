#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/frontend
./rep2.sh fe2_fbh "FE_FB=1 FE_FB_HALF=1"
./rep2.sh fe2_fb1 "FE_FB=1 FE_FB_PX=1.0"
cd /data/backups/rganapa/Sebastian/eecs116_projects
OPENBLAS_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.fresh.run_fresh --name fe2_fb --wasm research/results/single_model/fe2_fb_r0/solution.wasm --workers 24 > research/single_model/frontend/log_fresh_fe2_fb.txt 2>&1
echo done > research/single_model/frontend/queue3.done
