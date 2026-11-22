#!/bin/bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/eecs116_projects
F=research/single_model/linejac
while [ ! -f "$F/tables/ajgb4_r2__st1conf.json" ]; do sleep 10; done
printf '%s\n' 60 > "$F/logs/ajc.workers"
