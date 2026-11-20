#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/bulk
M2="MAP_MODE=1 MAP_AGE=100 MAP_ANG=40 MAP_TRY=12 MAP_ZNCC=0.85"
nohup ./q.sh bk_wd10i.fresh.txt "bk_m4|$M2 MAP_AGE=60 MAP_COOL=30 MAP_TRY=20 MAP_S=10" "bk_m3|$M2 MAP_SIG0=0.05 MAP_SIGD=0.03" > /dev/null 2>&1 &
nohup ./q.sh bk_wd10i.171.txt "bk_i2map|ITER_UPD=2 $M2" "bk_m5|$M2 MAP_SIG0=0.2 MAP_SIGD=0.1" > /dev/null 2>&1 &
