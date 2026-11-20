#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/bulk
nohup ./q.sh bk_gyro056.fresh.txt "bk_map1|MAP_MODE=1" "bk_wd14|WIN_BIG=14 WIN_T0=10" > /dev/null 2>&1 &
nohup ./q.sh bk_iter3.fresh.txt "bk_map2|MAP_MODE=1 MAP_AGE=100 MAP_ANG=40 MAP_TRY=12 MAP_ZNCC=0.85" "bk_wd10i|WIN_BIG=10 WIN_T0=10 ITER_UPD=2" > /dev/null 2>&1 &
