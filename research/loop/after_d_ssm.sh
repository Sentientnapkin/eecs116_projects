#!/bin/bash
# Start the GRU D0/D2 pair after the SSM D-series finishes (SSM comparison has priority).
cd "$(dirname "$0")/.."
while pgrep -f "output $PWD/results/loop/D[012]-ssm" >/dev/null; do sleep 60; done
./odometry_env.sh launch.py D0-gru D2-gru
echo "$(date +%H:%M) launched D0-gru D2-gru"
