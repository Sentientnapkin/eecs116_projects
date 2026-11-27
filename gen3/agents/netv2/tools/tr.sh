#!/bin/bash
# tr.sh NAME [lv4 args...] : train on GPU 5 only -> logs/NAME.log
N=$1; shift
cd /data/backups/rganapa/Sebastian/gen3/agents/netv2/tools
OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 CUDA_VISIBLE_DEVICES=5 /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B lv4.py --name $N "$@" > ../logs/$N.log 2>&1
