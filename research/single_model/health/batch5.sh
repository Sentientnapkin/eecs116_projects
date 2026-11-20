#!/bin/bash
H=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/health
( $H/run4.sh v3head_c2 "PRIOR_MODE=3 PRI_LAT_STD=0.5 PRI_VZ_STD=0.3 HC_STARVE=1 PRI_Z_STD=0.8" 2>&1 | grep -v finished | cut -c1-250 > $H/arm_v3head_c2.txt ) &
sleep 20
( $H/run5.sh c4 "PRI_LAT_STD=0.5 PRI_VZ_STD=0.3 PRI_Z_STD=0.8" 2>&1 | grep -v finished | cut -c1-250 > $H/arm_c4.txt ) &
wait
