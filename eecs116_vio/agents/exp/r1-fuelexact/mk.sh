#!/bin/bash
# mk.sh OUT.wasm [EXTRA -D flags] : origin/main base_sn.c -> patches -> r1.c -> wasm (WSL; flags.txt defines + F2 compiler flags)
set -e
H=/mnt/c/Users/alexa/Projects/eecs_116/eecs116_projects/eecs116_vio/agents/exp/r1-fuelexact
cd $H
python3 tools/patch_upd.py src/base_sn.c /tmp/r1fe_1.c > /dev/null
python3 tools/patch_gate.py /tmp/r1fe_1.c /tmp/r1fe_2.c > /dev/null
python3 tools/patch_s.py /tmp/r1fe_2.c r1.c > /dev/null
F2="-mllvm -disable-lsr -mllvm -unroll-threshold=3000 -mllvm -unroll-max-count=16 -mllvm -inline-threshold=1000"
bash bld.sh r1.c "$1" "$2" "${F2X-$F2}"
