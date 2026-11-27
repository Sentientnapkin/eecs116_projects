#!/bin/bash
set -euo pipefail
TASK=/tmp/vio_loop2/fuel
BULK=/dev/shm/vio_loop2/fuel
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
$PY "$TASK/start_profile.py" > "$TASK/profile_build.log" 2>&1
$PY /data/backups/rganapa/Sebastian/gen3/research/i1/prof_run.py "$BULK/profile.wasm" "$TASK/profile_flights.txt" "$BULK/profile" 4 > "$TASK/profile_eval.log" 2>&1
