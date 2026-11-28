#!/bin/bash
# pp.sh SRC.c OUT.txt : active-line view of SRC.c under the preserved_best flags
H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r2-fuelexact
CL=$HOME/ws_r2fe/build/toolchain/wasi-sdk/bin/clang
DEFS=$(tr -d '\r' < $H/src/flags.txt)
cp "$1" /tmp/r2fe_solution.c
$CL --target=wasm32-wasip1 -msimd128 -O3 -DNDEBUG -I$HOME/ws_r2fe/runtime/native $(for d in $DEFS; do printf -- '-D%s ' "$d"; done) -E /tmp/r2fe_solution.c -o /tmp/r2fe.i
python3 $H/tools/active.py "$1" /tmp/r2fe.i "$2"
