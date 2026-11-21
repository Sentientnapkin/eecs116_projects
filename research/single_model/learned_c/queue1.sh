#!/bin/bash
# queue1.sh REPS "n1 n2" "n3 n4" ... : evalrep (s171,f3) two at a time, REPS replicates
cd /data/backups/rganapa/Sebastian/eecs116_projects
export PYTHONPATH=. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python; L=research/single_model/learned_c; CM=research/single_model/fuel/CMakeLists_c1.txt
reps=$1; shift
for pair in "$@"; do
  for n in $pair; do $PY -B $L/evalrep.py $n $L/lc_$n.c --set s171,f3 --reps $reps --cmake $CM > $L/logs/ev_$n.log 2>&1 & done; wait
done
echo done > $L/logs/queue1.done
