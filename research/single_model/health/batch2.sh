#!/bin/bash
H=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/health
while pgrep -f batch1.sh >/dev/null; do sleep 15; done
r(){ $H/run2.sh "$1" "$2" 2>&1 | grep -v finished | cut -c1-250 > $H/arm_$1.txt; }
r recv035 "HC_REC=1 HC_REC_VSTD=0.35"
r recv035z3 "HC_REC=1 HC_REC_VSTD=0.35 HC_REC_Z=3.0"
r recspd22 "HC_REC=1 HC_REC_SPEED=2.2 HC_REC_Z=3.0"
r rectri04 "HC_REC=1 HC_REC_TRIFAIL=0.4 HC_REC_Z=3.0"
r recused7 "HC_REC=1 HC_REC_MINUSED=7 HC_REC_Z=3.0"
