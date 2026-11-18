#!/bin/bash
# Usage: ./odometry_env.sh odometry_data.py|odometry_train.py|odometry_hub.py [args...]
set -euo pipefail
cd "$(dirname "$0")"
stage1_data="$PWD/../../../../Final Project/classical_vio/research/data"
bench_dir="$PWD/../../../../Final Project/viobench"
export PYTHONPATH="$bench_dir:$stage1_data/local-python:$PWD"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4 PYTHONHASHSEED=0 PYTORCH_ENABLE_MPS_FALLBACK=1
script="$1"; shift
exec /opt/miniconda3/bin/python -B -c 'import sys, runpy; sys.path.append("/opt/miniconda3/envs/eecs116/lib/python3.10/site-packages"); s=sys.argv[1]; sys.argv=sys.argv[1:]; runpy.run_path(s, run_name="__main__")' "$script" "$@"
