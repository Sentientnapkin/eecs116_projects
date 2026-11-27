#!/bin/bash
# usage: runb.sh queue.txt pool   lines: name flags...  (builds from src/ins_P2.c, evals on pool)
cd /data/backups/rganapa/Sebastian/gen3/research/n3
PY=../../../venv-teacher/bin/python
while read name flags; do
  [ -z "$name" ] && continue
  [ -f logs/$name.$2.done ] && continue
  [ -f builds/$name/solution.wasm ] || python3 mk.py $name "$flags" src/ins_P2.c > logs/$name.mk 2>&1
  while [ $(cut -d. -f1 /proc/loadavg) -gt 170 ]; do sleep 60; done
  $PY ev.py n3_$name builds/$name/solution.wasm pools/$2 8 > logs/$name.$2.ev 2>&1; touch logs/$name.$2.done
done < $1
touch logs/$(basename $1).$2.done
