#!/bin/bash
H=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/health
while pgrep -f batch2.sh >/dev/null; do sleep 15; done
r(){ $H/run2.sh "$1" "$2" 2>&1 | grep -v finished | cut -c1-250 > $H/arm_$1.txt; }
r plat035 "PRI_LAT_STD=0.35"
r plat07 "PRI_LAT_STD=0.7"
r c1 "PRI_LAT_STD=0.5 PRI_VZ_STD=0.3 HC_STARVE=1"
r c2 "PRI_LAT_STD=0.5 PRI_VZ_STD=0.3 HC_STARVE=1 PRI_Z_STD=0.8"
r c3 "PRI_LAT_STD=0.5 PRI_VZ_STD=0.3 HC_STARVE=1 HC_STARVE_SCALE=0.4"
