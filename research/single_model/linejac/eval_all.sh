#!/bin/bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/eecs116_projects
F=research/single_model/linejac
N=$1; DEFS=$2
ST=/data/backups/rganapa/Sebastian/tmp/st_pools
LV=/data/backups/rganapa/Sebastian/tmp/lv_pools
for R in 0 1 2; do
 SUF=""; NUDGE=""
 if [ "$R" = 1 ]; then SUF=_r1; NUDGE="PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0"; fi
 if [ "$R" = 2 ]; then SUF=_r2; NUDGE="PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0"; fi
 bash "$F/bp.sh" "$N$SUF" lj.c "$DEFS $NUDGE" "$ST/st2dev" "$LV/st3" "$ST/st2conf" "$LV/fdev" "$LV/fconf" "$ST/st1dev" "$ST/st1conf"
done
