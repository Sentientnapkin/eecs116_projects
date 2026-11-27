#!/bin/bash
cd /data/backups/rganapa/Sebastian/gen3
while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
[ -f research/i2/logs/eval_v3.done ] || { ../venv-teacher/bin/python -B evalpool.py i2_dbg research/i2/builds/dbg/solution.wasm pools/v3val 8 && touch research/i2/logs/eval_v3.done; }
