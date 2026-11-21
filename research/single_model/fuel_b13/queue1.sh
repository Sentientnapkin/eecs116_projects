#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
bash $E cl5 b13y.c "MAX_CLONES=5" 0
bash $E gate2 b13y.c "GATE2=1" 0
bash $E fb4 b13y.c "FB_PERIOD=4" 0
bash $E kit3 b13y.c "KLT_ITERS=3" 0
bash $E det2 b13y.c "DET_PERIOD=2" 0
bash $E ith b13y.c "ITER_TH=0.1" 0
