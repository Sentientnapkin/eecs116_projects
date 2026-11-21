#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
E=research/single_model/fuel_b13/ev.sh
bash $E c1 b13q2.c "" 0
bash $E c1kr3 b13q2.c " KLT_R=3" 0
bash $E c1g86 b13q2.c " GRID_X=8 GRID_Y=6" 0
bash $E c1kit3 b13q2.c " KLT_ITERS=3" 0
bash $E c1mt4 b13q2.c " MAP_TRY=4" 0
