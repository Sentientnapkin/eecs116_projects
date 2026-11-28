#!/bin/bash
# asm.sh SRC.c OUT.s : wasm assembly of SRC.c with the build's flags
H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r1-fuelexact
CL=$HOME/ws_r1fe/build/toolchain/wasi-sdk/bin/clang
DEFS=$(tr -d '\r' < $H/src/flags.txt)
cp "$1" /tmp/r1fe_asm.c
$CL --target=wasm32-wasip1 -O3 -DNDEBUG -O2 -msimd128 -I$HOME/ws_r1fe/runtime/native $(for d in $DEFS; do printf -- '-D%s ' "$d"; done) -O3 $3 -S /tmp/r1fe_asm.c -o "$2" 2>/dev/null
