#!/bin/bash
# variant.sh NAME [-DFLAG=VAL ...]: build a host library with overrides and score it on all local flight sets.
# Writes night/var_NAME.txt (per-flight lines + one summary line per set).
NAME=$1; shift
SRC=/mnt/c/Users/alexa/Projects/eecs116_vio/csol/solution/solution.c
gcc -O2 -shared -fPIC -I "$HOME/ws_c/runtime/native" "$@" -o "$HOME/ws_c/libvio_$NAME.so" "$SRC" -lm || exit 1
cd /mnt/c/Users/alexa/Projects/eecs116_vio/proto
OUT=night/var_$NAME.txt; echo "flags: $*" > $OUT
for s in NIGHT AGILE2 TUNE HELDOUT; do echo "=== $s" >> $OUT; bash pyrun.sh $s diag.py lib=$HOME/ws_c/libvio_$NAME.so >> $OUT 2>&1; done
echo "$NAME $(grep MEAN $OUT | awk '{printf "%s/%s  ", $3, $5}')  $*" >> night/variants_summary.txt
