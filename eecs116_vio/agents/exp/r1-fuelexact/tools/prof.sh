#!/bin/bash
# prof.sh WASM OUTDIR FLIGHT... : prof.py under the heavy-job lock (flights by name from ~/data/s3match)
source ~/.venv/bin/activate
H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r1-fuelexact
W=$1; O=$2; shift 2
Z=""; for f in "$@"; do Z="$Z $HOME/data/s3match/$f.zip"; done
exec 9> "$HOME/data/.heavy.lock"; flock 9
cd /tmp && python $H/tools/prof.py $W $O $Z -j ${J:-6}
