#!/bin/bash
# rep2.sh name "defines": 3 replicates, pairs (r0,r1 concurrent, then r2)
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/frontend
./run2.sh ${1}_r0 "$2" &
./run2.sh ${1}_r1 "$2 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0" &
wait
./run2.sh ${1}_r2 "$2 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0"
