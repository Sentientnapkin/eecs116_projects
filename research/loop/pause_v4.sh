#!/bin/bash
# Stop the v4 data run right after its next completed checkpoint (resumable; synced to the Hub).
cd "$(dirname "$0")/.."
run=results/loop/data-teacher-v4-ssm-recipe
until ls $run/checkpoints/*/complete.json >/dev/null 2>&1; do sleep 30; done
sleep 120   # let the Hub push for that epoch finish
pkill -f "output $PWD/$run" || pkill -f "data-teacher-v4-ssm-recipe --hub-repo"
echo "$(date +%H:%M) paused v4 after $(ls $run/checkpoints | tail -1)"
