#!/bin/bash
# Launch the GRU D0/D2 pair once the attitude run releases its GPU share.
cd "$(dirname "$0")/.."
while pgrep -f "output $PWD/results/loop/ssm-att-nopatience" >/dev/null; do sleep 60; done
./odometry_env.sh launch.py D0-gru D2-gru
echo "$(date +%H:%M) launched D0-gru D2-gru"
