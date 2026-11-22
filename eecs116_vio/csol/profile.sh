#!/bin/bash
# Fuel ablation: build variants with one piece reduced and measure fuel on one fast flight.
EP=/home/alexa/data/agile2/sim-ProcTHOR-Train-9-0000.zip
run() { name=$1; shift
  bash /mnt/c/Users/alexa/Projects/eecs116_vio/csol/build.sh "prof_$name" "$@" > /dev/null 2>&1 || { echo "$name: build failed"; return; }
  echo "$name ($*): $(EPISODES=$EP bash /mnt/c/Users/alexa/Projects/eecs116_vio/csol/evaluate.sh vio_prof_$name.wasm | tail -1)"; }
run new_default
run back4        BACK_LEVELS=4
run coarse5      COARSE_ITERATIONS=5 COARSE_EPS=0.0009f
