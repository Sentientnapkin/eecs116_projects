#!/bin/bash
H=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/health
r(){ $H/run.sh "$1" "$2" 2>&1 | grep -v finished | cut -c1-250 > $H/arm_$1.txt; }
r lim1 "HC_LIM=1"
r lim1reset "HC_LIM=1 HC_RESET=1"
r lim2tight "HC_LIM=1 HC_VMAX=3.0 HC_VZMAX=1.2"
r nis309 "HC_NIS_Z=3.09"
r starve "HC_STARVE=1"
r pz08 "PRI_Z_STD=0.8"
r pvz03 "PRI_VZ_STD=0.3"
r pvh08 "PRI_VH_STD=0.8"
r plat05 "PRI_LAT_STD=0.5"
