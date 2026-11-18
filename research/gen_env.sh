#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
stage1_data="$PWD/../../../../Final Project/classical_vio/research/data"
bench_dir="$PWD/../../../../Final Project/viobench"
export PYTHONPATH="$bench_dir:$stage1_data/sim-python:$stage1_data/local-python"
export HYPERLUX_CACHE_DIR="$stage1_data/hyperlux-cache"
export CONTA_CACHE="$stage1_data/scene-cache"
export VIOBENCH_CACHE="$PWD/data/hyperlux-cache"
export PYTHONHASHSEED=0
exec /opt/miniconda3/envs/eecs116/bin/python -B "$@"
