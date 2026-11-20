#!/bin/bash
# usage: rep.sh name src.c "defines"   -> runs 3 chaos replicates name_r0..r2 (pixel std / detect threshold nudges)
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/tails
./run.sh ${1}_r0 $2 "$3" &
./run.sh ${1}_r1 $2 "$3 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0" &
./run.sh ${1}_r2 $2 "$3 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0" &
wait
