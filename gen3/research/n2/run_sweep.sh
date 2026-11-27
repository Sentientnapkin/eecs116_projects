#!/bin/bash
cd /data/backups/rganapa/Sebastian/gen3/research/n2
PY=../../../venv-teacher/bin/python
while read name flags; do
  [ -f logs/$name.done ] && continue
  python3 mk.py $name "$flags" src/ins_C.c > logs/$name.mk 2>&1
  $PY ev.py n2_$name builds/$name/solution.wasm pools/s40 8 > logs/$name.ev 2>&1; touch logs/$name.done
done < queue1.txt
touch sweep1.done
