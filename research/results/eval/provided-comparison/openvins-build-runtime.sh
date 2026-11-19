#!/bin/bash
# Step 1 of the unchanged build: the wasm Python/OpenCV runtime recipe the OpenVINS CMake would invoke,
# run directly so the cross-compiler's CC is not inherited by the host CPython configure.
set -euo pipefail
W=/dev/shm/sebastian-vio/viobench/viobench/solution
exec env -i HOME=/data/backups/rganapa/Sebastian TMPDIR=/dev/shm/sebastian-vio/tmp \
  PATH=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin:/usr/bin:/bin \
  BUILD=$W/build/runtime bash $W/runtime/python/build.sh
