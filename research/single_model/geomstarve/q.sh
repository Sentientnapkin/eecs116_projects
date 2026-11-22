#!/bin/bash
# q.sh JOBFILE [PAR] : run lines of JOBFILE (shell lines, e.g. './bp.sh NAME "DEFS" POOLS', may start with REP=1) PAR at a time
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/geomstarve
J=$1; P=${2:-2}; B=$(basename $J .txt); L=logs/q_$B.txt; D=logs/jl_$B; mkdir -p $D
i=0; grep -v '^#' $J | grep -v '^\s*$' | while IFS= read -r line; do i=$((i+1)); printf '%s\n' "$line" > $D/$(printf %03d $i).sh; done
ls $D/*.sh | xargs -P $P -n 1 bash >> $L 2>&1
echo DONE >> $L
