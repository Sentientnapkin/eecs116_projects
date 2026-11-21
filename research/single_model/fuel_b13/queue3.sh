#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
C1="MAX_CLONES=5 GATE2=1 DET_PERIOD=2 ITER_TH=0.1 MAP_SPREAD=1 LC_SPREAD=4"
bash $E b16exact b16q.c "" 0
bash $E s1 b16q.c "$C1 KLT_R=3" 0
bash $E s1b b16q.c "$C1 KLT_R=3 MAP_TRY=4 KLT_ITERS=4" 0
