#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
while pgrep -f "fuel_b13/queue8.sh" >/dev/null; do sleep 10; done
B="VIS4=1 MAP_TRY=2 FB_PERIOD=1 VIS4_VEL=1.0 LEVELS=3 LC_SPREAD=4 LC_PSPLIT=1"
bash $E w1 b16s_q9.c "$B" 0
bash $E w2 b16s_q9.c "$B MAX_CLONES=5 GATE2=1 ITER_TH=0.1" 0
bash $E w3 b16s_q9.c "$B MAX_CLONES=4 GATE2=1 ITER_UPD=1 CAP_OLD=4 CAP_LOST=5" 0
bash $E w4 b16s_q9.c "$B MAX_CLONES=5 GATE2=1 ITER_TH=0.1 KLT_R=3" 0
