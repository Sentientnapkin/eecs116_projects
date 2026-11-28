#!/bin/bash
# Validate local regeneration on a flight we have, then regenerate the three missing holdout flights.
source "$HOME/.venv/bin/activate"; cd "$HOME"; mkdir -p data/regen
export HYPERLUX_BACKEND=GENERIC HYPERLUX_CACHE_DIR=$HOME/.cache/hyperlux-generic VIOBENCH_CACHE=$HOME/.cache/viobench-generic
B=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/b16
gen() { echo "$(date +%T) start $1"; python $B/regen_flight.py data/regen/$1.zip hssd-train $2 $3 $4 $5 2>&1 | grep -v conta | tail -3; echo "$(date +%T) done $1"; }
gen fast-102816009-60 102816009 972042 K2 0
python - <<'PY' || exit 1
from viobench.tools.datasets.sources import episodes
import numpy as np, os
a = next(episodes([os.path.expanduser('~/data/ho240/fast-102816009-60.zip')])).ground_truth_state()
b = next(episodes([os.path.expanduser('~/data/regen/fast-102816009-60.zip')])).ground_truth_state()
n = min(len(a), len(b)); print('VALIDATE frames', len(a), len(b), 'max pos diff m', float(np.abs(a[:n, :3] - b[:n, :3]).max()))
PY
gen fastmid-102816009-51 102816009 982115 K2 21.3
gen fastmid-105515175_173104107-52 105515175_173104107 982203 K 38.5
gen fastmid-102816009-52 102816009 982116 K2 30.75
echo ALLDONE
