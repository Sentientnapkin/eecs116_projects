#!/bin/bash
# tr.sh TAG [lv5 args...] : GPU 5 only -> logs/TAG.log
T=$1; shift
cd /data/backups/rganapa/Sebastian/gen3/agents/smallnet/tools
OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 CUDA_VISIBLE_DEVICES=5 nohup /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B lv5.py --tag $T "$@" > ../logs/$T.log 2>&1 &
echo $! > ../logs/$T.pid
