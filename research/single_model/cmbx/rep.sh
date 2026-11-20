#!/bin/bash
# rep.sh name "defines": 3 replicates (r0,r1 concurrent, then r2); results in research/results/single_model/<name>_r*
D=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/cmbx
$D/run.sh ${1}_r0 "$2" &
$D/run.sh ${1}_r1 "$2 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0" &
wait
$D/run.sh ${1}_r2 "$2 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0"
