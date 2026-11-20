#!/bin/bash
H=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/health
while pgrep -f batch3.sh >/dev/null; do sleep 15; done
r(){ $H/run3.sh "$1" "$2" 2>&1 | grep -v finished | cut -c1-250 > $H/arm_$1.txt; }
H3="PRIOR_MODE=3"
r v3head "$H3"
r v3head_starve "$H3 HC_STARVE=1"
r v3head_rectri04 "$H3 HC_REC=1 HC_REC_TRIFAIL=0.4 HC_REC_Z=3.0"
r v3head_recv035z3 "$H3 HC_REC=1 HC_REC_VSTD=0.35 HC_REC_Z=3.0"
r v3head_plat05 "$H3 PRI_LAT_STD=0.5"
r v3head_pvz03 "$H3 PRI_VZ_STD=0.3"
r v3head_nis309 "$H3 HC_NIS_Z=3.09"
