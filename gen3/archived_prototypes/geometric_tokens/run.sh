#!/bin/bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/tmp/vio_loop3/geometric_tokens
source /data/backups/rganapa/Sebastian/venv-teacher/bin/activate
timeout 7200s python -u cache.py
timeout 7200s python -u train.py
