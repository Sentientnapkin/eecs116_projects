#!/bin/bash
set -e
F=research/single_model/stlong
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
V=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
export CUDA_VISIBLE_DEVICES=1 CUDA_CACHE_PATH=/data/backups/rganapa/Sebastian/tmp/stlong_cuda_cache
$PY -B $F/direct.py --run $F/runs/pilot --out pilot
$PY -B $F/build.py --name pilot --run $F/runs/pilot
$V -B $F/evaluate.py --name pilot --workers 48
$PY -B $F/compare.py pilot --reps 1
$PY -B $F/calibrate.py pilot
