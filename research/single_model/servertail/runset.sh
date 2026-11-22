#!/bin/bash
# runset.sh POOLS... : run the standard wasm list (WASMS env "name=path ...") over pools
R=/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model
for nw in $WASMS; do n=${nw%%=*}; w=${nw#*=}; [ "$w" = "$nw" ] && w=$R/st_$n/solution.wasm
  for P in "$@"; do ./rp.sh $n $w $P ${W:-32}; done; done
