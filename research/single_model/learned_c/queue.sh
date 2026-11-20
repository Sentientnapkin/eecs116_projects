#!/bin/bash
# runs evalrep jobs two at a time: queue.sh "name1 name2" "name3 name4" ...
cd /data/backups/rganapa/Sebastian/eecs116_projects
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python; L=research/single_model/learned_c; CM=research/single_model/fuel/CMakeLists_c1.txt
for pair in "$@"; do
  for n in $pair; do $PY -B $L/evalrep.py $n $L/lc_$n.c --set s171,f3 --cmake $CM > $L/logs/ev_$n.log 2>&1 & done; wait
done
echo done > $L/logs/queue.done
