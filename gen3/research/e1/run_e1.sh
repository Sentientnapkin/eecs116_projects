#!/bin/bash
cd /data/backups/rganapa/Sebastian/gen3
for m in w_nf4 w_nf8 w_nf16 w_nf8_s5; do
  [ -f research/e1/logs/$m.done ] && continue
  ../venv-teacher/bin/python -B research/e1/ev.py e1_${m}_s40 research/e1/builds/$m/solution.wasm research/e1/pools/s40 8 > research/e1/logs/$m.log 2>&1 && touch research/e1/logs/$m.done
done
touch research/e1/logs/ALL.done
