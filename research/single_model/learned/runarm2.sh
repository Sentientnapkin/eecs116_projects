#!/bin/bash
# usage: DEFS="..." runarm2.sh <arm> <tag> <make_arm args>; defines separated via the env var passed by xargs line "DEFS=..." not supported, so we parse a leading --defs=
cd /data/backups/rganapa/Sebastian/eecs116_projects
n=$1; t=$2; shift 2
defs=""
args=()
for a in "$@"; do case $a in --defs=*) defs="${a#--defs=}";; *) args+=("$a");; esac; done
DEFS="$defs" research/single_model/learned/runarm.sh $n $t "${args[@]}"
