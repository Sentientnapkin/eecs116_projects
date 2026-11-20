#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/bulk
M2="MAP_MODE=1 MAP_AGE=100 MAP_ANG=40 MAP_TRY=12 MAP_ZNCC=0.85"
nohup ./q.sh bk_m3.fresh.txt "bk_m6|$M2 MAP_N=512 MAP_SUB=1 MAP_PIX=1.5" "bk_m8|$M2 MAP_S=12" > /dev/null 2>&1 &
nohup ./q.sh bk_m5.fresh.txt "bk_m7|$M2 MAP_NEAR=1" "bk_i2m6|ITER_UPD=2 $M2 MAP_N=512 MAP_SUB=1 MAP_PIX=1.5" > /dev/null 2>&1 &
