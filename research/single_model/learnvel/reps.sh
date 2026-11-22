#!/bin/bash
# reps.sh NAME SRC "DEFS" POOL... : builds+runs rep r1 and r2 (r0 assumed done separately unless R0=1)
R1="PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0"; R2="PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0"
N=$1; S=$2; D=$3; shift 3
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model
[ "$R0" = 1 ] && bash learnvel/bp.sh $N $S "$D" "$@"
bash learnvel/bp.sh ${N}_r1 $S "$D $R1" "$@"
bash learnvel/bp.sh ${N}_r2 $S "$D $R2" "$@"
