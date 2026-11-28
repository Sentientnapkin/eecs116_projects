#!/bin/bash
# rc.sh TAG [REF_TAG...] : run6 on $H/TAG.wasm (or src/TAG.wasm) into ~/r2fe/run_TAG, then cmp.py against each REF_TAG run
H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r2-fuelexact
T=$1; shift
W=$H/$T.wasm; [ -f $W ] || W=$H/src/$T.wasm
bash $H/tools/run6.sh $W ~/r2fe/run_$T > /dev/null 2>&1
source ~/.venv/bin/activate
for R in "$@"; do echo "== $T vs $R"; python $H/tools/cmp.py ~/r2fe/run_$R ~/r2fe/run_$T | ${CMPF:-tail -1}; done
