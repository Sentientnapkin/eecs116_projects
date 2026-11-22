#!/bin/bash
# Speed stats + v3 (host build of solution.c) vs do-nothing on every overnight group, including mid-flight starts.
source "$HOME/.venv/bin/activate"; cd /mnt/c/Users/alexa/Projects/eecs116_vio/proto
for g in $HOME/data/night/*/; do
  echo "=================== $(basename $g) ==================="
  python flight_stats.py $g 2>&1 | grep -v '^conta:'
  python run.py $g --variants zeros --try v3:impl=c --crops 0 15 2>&1 | grep -v '^conta:'
done
