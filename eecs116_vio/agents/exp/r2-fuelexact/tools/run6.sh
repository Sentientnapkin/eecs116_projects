#!/bin/bash
# run6.sh WASM OUTDIR [FLIGHTS...] : prof.py (poses, per-frame fuel) on the 6 profiling flights (or the given ones)
H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r2-fuelexact
W=$1; O=$2; shift 2
[ $# -gt 0 ] || set -- s3v3te-ro-9300648 s3v3te-ro-9300784 s3v3te-ro-9300867 s3va-ro-9010255 s3v3te-wa-h9500246 s3te-fo-9011115
rm -rf $O; bash $H/tools/prof.sh $W $O "$@" | grep -v "^s3" ; true
