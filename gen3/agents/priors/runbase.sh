#!/bin/bash
cd /data/backups/rganapa/Sebastian/gen3
while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
../venv-teacher/bin/python -B evalpool.py gslvlj /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/linejac/final/gslv_linejac_arith.wasm pools/$1 20 > agents/priors/logs/gslvlj__$1.log 2>&1
echo "gslvlj $1 done $(date +%T)"
