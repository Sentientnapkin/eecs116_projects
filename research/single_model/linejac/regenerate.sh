#!/bin/bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/eecs116_projects
F=research/single_model/linejac
for SCRIPT in make_source.py line_simd.py forward.py chol.py governor.py normal.py; do python3 "$F/$SCRIPT"; done
