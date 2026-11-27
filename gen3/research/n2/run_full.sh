#!/bin/bash
cd /data/backups/rganapa/Sebastian/gen3/research/n2
PY=../../../venv-teacher/bin/python
for p in v3val v1val; do $PY ev.py n2_c3 builds/c3/solution.wasm ../../pools/$p 8 > logs/full_c3_$p.ev 2>&1; done
touch full.done
