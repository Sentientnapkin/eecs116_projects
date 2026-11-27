#!/usr/bin/env bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/gen3
python - <<'PY'
import json
m=json.load(open('/tmp/vio_loop2/shared/manifest.json'))
open('/tmp/vio_loop2/geometry/queue/panel24.txt','w').write(''.join('/data/backups/rganapa/Sebastian/gen3/pools/v3val/'+x+'.zip\n' for x in m['panels']['screen24']))
PY
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/data/backups/rganapa/Sebastian/venv-teacher/bin/python -B /tmp/vio_loop2/geometry/src/robustness.py /tmp/vio_loop2/geometry/queue/panel24.txt /tmp/vio_loop2/geometry/out/r1 2 >> /tmp/vio_loop2/geometry/logs/r1.log 2>&1
