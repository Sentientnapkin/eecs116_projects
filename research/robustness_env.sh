#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
stage1_data="$PWD/../../../../Final Project/classical_vio/research/data"
bench_dir="$PWD/../../../../Final Project/viobench"
export PYTHONPATH="$bench_dir:$stage1_data/local-python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 PYTHONHASHSEED=0
exec /opt/miniconda3/bin/python -B -c 'import sys; sys.path.append("/opt/miniconda3/envs/eecs116/lib/python3.10/site-packages"); from robustness import main; main()' "$@"
