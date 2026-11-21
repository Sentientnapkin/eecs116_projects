#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
while pgrep -f "fuel_b13/queue9.sh" >/dev/null; do sleep 10; done
G="KLT_R=3 GATE2=1 ITER_TH=0.1 DET_PERIOD=2"
bash $E g1 b16q.c "$G" 0
bash $E g1r1 b16q.c "$G" 1
bash $E g1r2 b16q.c "$G" 2
