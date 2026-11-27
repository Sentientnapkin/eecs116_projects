#!/bin/bash
set -euo pipefail
cd /tmp/vio_loop3/efficient_round2
exec /usr/bin/timeout --signal=TERM --kill-after=20s 7200s /data/backups/rganapa/Sebastian/venv-teacher/bin/python -u run_queue.py >> runner.log 2>&1
