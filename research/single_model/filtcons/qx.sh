#!/bin/bash
# qx.sh JOBFILE [W] : jobs "NAME|EXTRA DEFS|POOLS(space sep, short names)" appended to HM40 defines; runs sequentially, pops lines
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/filtcons
J=$1; export W=${2:-24}; P=/data/backups/rganapa/Sebastian/tmp/st_pools
while true; do
  L=$(head -1 $J); [ -z "$L" ] && break; sed -i 1d $J
  N=${L%%|*}; R=${L#*|}; X=${R%%|*}; PS=${R#*|}
  PP=""; for p in $PS; do [ $p = fresh03 ] && PP="$PP /data/backups/rganapa/Sebastian/tmp/fc_pools/fresh03" || PP="$PP $P/$p"; done
  ./bp.sh $N fc.c "$(cat hm40.defs) $X" $PP
done
