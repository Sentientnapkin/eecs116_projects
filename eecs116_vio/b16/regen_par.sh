#!/bin/bash
# Regenerate the missing holdout flights on the CPU renderer: the two bad ones in parallel, then the typical one.
source "$HOME/.venv/bin/activate"; cd "$HOME"; mkdir -p data/regen
export HYPERLUX_BACKEND=GENERIC HYPERLUX_CACHE_DIR=$HOME/.cache/hyperlux-generic VIOBENCH_CACHE=$HOME/.cache/viobench-generic
B=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/b16
gen() { echo "$(date +%T) start $1"; python $B/regen_flight.py data/regen/$1.zip hssd-train $2 $3 $4 $5 > data/regen/$1.log 2>&1; echo "$(date +%T) done $1 exit $? $(tail -1 data/regen/$1.log)"; }
( gen fastmid-102816009-51 102816009 982115 K2 21.3; gen fastmid-102816009-52 102816009 982116 K2 30.75 ) &
gen fastmid-105515175_173104107-52 105515175_173104107 982203 K 38.5 &
wait; echo ALLDONE
