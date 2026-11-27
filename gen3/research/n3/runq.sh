#!/bin/bash
# usage: runq.sh queue.txt   (lines: name pool) ; builds must exist; skips done
cd /data/backups/rganapa/Sebastian/gen3/research/n3
PY=../../../venv-teacher/bin/python
while read name pool; do
  [ -z "$name" ] && continue
  [ -f logs/$name.$pool.done ] && continue
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
  $PY ev.py n3_$name builds/$name/solution.wasm pools/$pool 8 > logs/$name.$pool.ev 2>&1; touch logs/$name.$pool.done
done < $1
touch logs/$(basename $1).done
