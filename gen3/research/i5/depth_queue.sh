#!/bin/bash
set -euo pipefail
cd /data/backups/rganapa/Sebastian/gen3/research/i5
R=/data/backups/rganapa/Sebastian
export CUDAARCHS=90 CONTA_CACHE=$R/gen/conta HYPERLUX_CACHE_DIR=$PWD/cache XDG_CACHE_HOME=$R/gen/xdg HF_HOME=$R/hf PATH=$R/venv-sim11/bin:$PATH TMPDIR=$PWD/tmp CUDA_VISIBLE_DEVICES=5 OMP_NUM_THREADS=2
OUT=$R/gen3/research/overnight_20261127/depth
mkdir -p "$OUT" "$R/tmp/vio_overnight/depth"
exec 9>"$OUT/queue.lock"; flock 9
python -u depth_queue.py >>"$OUT/queue.log" 2>&1
