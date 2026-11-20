#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/bulk
nohup ./q.sh bk_wd14.fresh.txt "bk_i2th05|ITER_UPD=2 ITER_TH=0.05" "bk_i2_r2|ITER_UPD=2 PIXEL_STD=1.5075 ACCEL_NOISE=0.2814" > /dev/null 2>&1 &
nohup ./q.sh bk_wd10i.fresh.txt "bk_i2_r1|ITER_UPD=2 ACCEL_NOISE=0.2828 KLT_MIN_EIG=2.01" "bk_i2_r3|ITER_UPD=2 DETECT_MIN_SCORE=995.0 KLT_MIN_EIG=2.02 PIXEL_STD=1.4925" > /dev/null 2>&1 &
