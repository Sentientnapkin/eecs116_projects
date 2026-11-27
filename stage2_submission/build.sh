#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${WASI_SDK_PATH:?Set WASI_SDK_PATH to wasi-sdk 34}"
: "${VIOBENCH_NATIVE_DIR:?Set VIOBENCH_NATIVE_DIR to viobench/solution/runtime/native in VIOBench 9b1b079}"
cmake -S . -B build \
  -DCMAKE_TOOLCHAIN_FILE="$WASI_SDK_PATH/share/cmake/wasi-sdk-p1.cmake" \
  -DVIOBENCH_NATIVE_DIR="$VIOBENCH_NATIVE_DIR" \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build
cmp solution.wasm build/solution.wasm
sha256sum -c SHA256SUMS
