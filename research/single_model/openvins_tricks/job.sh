#!/bin/bash
# usage: job.sh arm "defines" -> runs replicates oy_<arm>_r0..2 sequentially (the queue runs 2 jobs concurrently)
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/openvins_tricks
a=$1; d=$2
case "$d" in *PIXEL_STD*) p1=""; p2="";; *) p1="PIXEL_STD=1.515"; p2="PIXEL_STD=1.485";; esac
./run.sh oy_${a}_r0 "$d"
./run.sh oy_${a}_r1 "$d $p1 DETECT_MIN_SCORE=1010.0"
./run.sh oy_${a}_r2 "$d $p2 DETECT_MIN_SCORE=990.0"
