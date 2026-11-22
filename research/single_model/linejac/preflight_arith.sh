#!/bin/bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/eecs116_projects
F=research/single_model/linejac
while [ ! -f "$F/final/preflight/done" ]; do sleep 5; done
python3 "$F/verify_preflight.py"
bash "$F/preflight.sh" "$F/final/gslv_linejac_arith.wasm" "$F/final/preflight_arith"
python3 "$F/verify_preflight.py" final/preflight_arith
