#!/bin/bash
# buildprof.sh <src.c> <out.wasm> [extra clang flags]  -- profiling build (host import env.mark allowed)
TC=/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk; NAT=/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native
src=$1; out=$2; shift 2
$TC/bin/clang --sysroot $TC/share/wasi-sysroot --target=wasm32-wasip1 -O2 -msimd128 -DPROF -I$NAT -mexec-model=reactor -Wl,--initial-memory=67108864 -Wl,--strip-debug -Wl,--allow-undefined "$@" $src -o $out -lm 2>&1 | grep -E "error" 
