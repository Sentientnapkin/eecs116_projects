#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
while pgrep -f "run_fresh_fb --name k_cl5" >/dev/null; do sleep 10; done
bash $E v4d b16s_q6.c "VIS4=1 MAP_TRY=2 FB_PERIOD=1" 0
bash $E v4e b16s_q6.c "VIS4=1 MAP_TRY=2 FB_PERIOD=2" 0
bash $E k_kr3 b16q.c "KLT_R=3" 0
bash $E k_g2ith b16q.c "GATE2=1 ITER_TH=0.1" 0
bash $E k_det2 b16q.c "DET_PERIOD=2" 0
bash $E k_msls b16q.c "MAP_SPREAD=1 LC_SPREAD=4" 0
