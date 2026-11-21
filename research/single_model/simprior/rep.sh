#!/bin/bash
# usage: rep.sh name "defines" -> 3 chaos replicates sp_X_r0..r2 sequentially started in parallel
D=/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/simprior
$D/run.sh ${1}_r0 "$2" &
$D/run.sh ${1}_r1 "$2 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0" &
$D/run.sh ${1}_r2 "$2 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0" &
wait
