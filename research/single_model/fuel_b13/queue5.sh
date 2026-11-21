#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
while pgrep -f queue4.sh >/dev/null; do sleep 10; done
bash $E k_cl5 b16q.c "MAX_CLONES=5" 0
bash $E k_kr3 b16q.c "KLT_R=3" 0
bash $E k_g2ith b16q.c "GATE2=1 ITER_TH=0.1" 0
bash $E k_det2 b16q.c "DET_PERIOD=2" 0
bash $E k_msls b16q.c "MAP_SPREAD=1 LC_SPREAD=4" 0
