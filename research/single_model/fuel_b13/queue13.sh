#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
B="VIS4=1 MAP_TRY=2 FB_PERIOD=1 VIS4_VEL=1.0 LEVELS=3 LC_SPREAD=4 LC_PSPLIT=1"
bash $E w4r1 b16s_q9.c "$B MAX_CLONES=5 GATE2=1 ITER_TH=0.1 KLT_R=3" 1
bash $E w4r2 b16s_q9.c "$B MAX_CLONES=5 GATE2=1 ITER_TH=0.1 KLT_R=3" 2
bash $E w1r1 b16s_q9.c "$B" 1
bash $E w1r2 b16s_q9.c "$B" 2
