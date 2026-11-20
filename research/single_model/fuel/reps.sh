#!/bin/bash
# reps.sh name "defines"  -> three chaos replicates fuel_<name>_r0..r2 (same nudges as tails/rep.sh), run 3 sequentially
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/fuel
./runarms.sh "${1}_r0|$2" "${1}_r1|$2 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0" "${1}_r2|$2 PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0"
