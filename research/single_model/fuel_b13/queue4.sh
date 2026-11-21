#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
while pgrep -f queue3.sh >/dev/null; do sleep 10; done
V="VIS4=1 MAP_TRY=2 MAX_CLONES=5 GATE2=1 ITER_TH=0.1 LC_SPREAD=4"
bash $E v4a b16s_q4.c "$V KLT_R=3" 0
bash $E v4b b16s_q4.c "$V" 0
bash $E v4c b16s_q4.c "VIS4=1 MAP_TRY=2" 0
