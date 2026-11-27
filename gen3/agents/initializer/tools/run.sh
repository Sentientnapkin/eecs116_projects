#!/bin/bash
# run.sh NAME POOL WORKERS : evaluate builds/NAME/solution.wasm as ini_NAME on POOL (waits while load > 170)
cd /data/backups/rganapa/Sebastian/gen3
while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 20; done
../venv-teacher/bin/python -B evalpool.py ini_$1 agents/initializer/builds/$1/solution.wasm $2 $3 > agents/initializer/logs/$1__$(basename $2).txt 2>&1
