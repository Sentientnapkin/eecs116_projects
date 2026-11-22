#!/bin/bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/eecs116_projects
# Existing st3 may still be using 48 workers; start only after the next 32-worker pool.
while ! test -f research/single_model/linejac/logs/ajgb4_r1__st2dev.txt || ! head -1 research/single_model/linejac/logs/ajgb4_r1__st2dev.txt | grep -q 'workers=32'; do sleep 5; done
exec env TMPDIR=/data/backups/rganapa/Sebastian/tmp W=28 bash research/single_model/linejac/eval_all.sh ajc 'EDGE_AJAC=1 EDGE_ASIMD=1 LJ_FWD=1 LJ_CHOL=1'
