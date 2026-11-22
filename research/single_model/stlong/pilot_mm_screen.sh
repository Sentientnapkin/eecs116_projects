#!/bin/bash
set -e
F=research/single_model/stlong
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
V=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
export CUDA_VISIBLE_DEVICES=2 CUDA_CACHE_PATH=/data/backups/rganapa/Sebastian/tmp/stlong_cuda_cache
$PY -B $F/direct.py --run $F/runs/pilot_mm --out pilot_mm
$PY -B $F/build.py --name pilot_mm --run $F/runs/pilot_mm
$V -B $F/evaluate.py --name pilot_mm --workers 48
$PY -B $F/compare.py pilot_mm --reps 1
$PY -B $F/calibrate.py pilot_mm
