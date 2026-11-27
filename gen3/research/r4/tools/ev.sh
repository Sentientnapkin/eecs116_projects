#!/bin/bash
# ev.sh NAME WASM POOL [workers]: eval (waits while load > 170), names prefixed r4_
G=/data/backups/rganapa/Sebastian/gen3; cd $G
while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 30; done
../venv-teacher/bin/python -B evalpool.py r4_$1 $2 $3 ${4:-8} > research/r4/logs/ev_$1_$(basename $3).log 2>&1
