#!/bin/bash
# usage: fchain.sh name1 name2 ... ; runs fresh two at a time
cd /data/backups/rganapa/Sebastian/eecs116_projects
f(){ OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.simprior.fresh --name $1 --workers 24 > research/single_model/simprior/flog_$1.txt 2>&1; }
while [ $# -gt 0 ]; do f $1 & [ -n "$2" ] && f $2 & wait; shift; shift; done
