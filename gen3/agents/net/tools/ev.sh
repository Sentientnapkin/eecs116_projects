#!/bin/bash
# ev.sh NAME WASM POOL [workers]: shared evalpool (waits while load > 170)
cd /data/backups/rganapa/Sebastian/gen3
while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
../venv-teacher/bin/python -B evalpool.py $1 $2 $( [[ $3 == /* ]] && echo $3 || echo pools/$3 ) ${4:-14}
