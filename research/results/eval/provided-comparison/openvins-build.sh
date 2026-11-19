#!/bin/bash
# Unchanged build of VIOBench's provided OpenVINS example, pinned at upstream 9b1b079, on local tmpfs, clean env.
set -euo pipefail
B=/dev/shm/sebastian-vio/viobench
OUT=/data/backups/rganapa/Sebastian/baselines/openvins-9b1b079
exec env -i HOME=/data/backups/rganapa/Sebastian TMPDIR=/dev/shm/sebastian-vio/tmp \
  PATH=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin:/usr/bin:/bin \
  PYTHONPATH=$B CMAKE_BUILD_PARALLEL_LEVEL=16 MAKEFLAGS=-j16 \
  bash -c "mkdir -p /dev/shm/sebastian-vio/tmp && cd $B && git rev-parse HEAD && git status --short && \
    python -m viobench bundle viobench/solution/examples/native/openvins -o $OUT/openvins.wasm"
