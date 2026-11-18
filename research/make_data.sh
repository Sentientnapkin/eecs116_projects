#!/bin/sh
# Reproducible proxy sets (research). Train: ProcTHOR-Train-10..33; held-out scenes: ProcTHOR-Train-150..161.
set -e
PY=${PY:-/private/tmp/eecs116-reorg-env/bin/python}
train=""; for i in $(seq 10 33); do train="$train ProcTHOR-Train-$i"; done
val="";   for i in $(seq 150 161); do val="$val ProcTHOR-Train-$i"; done
for t in base mid agile; do
  $PY gen.py --tier $t --duration 60 --episodes 4 --seed 100 --scenes $train -o data/train
  $PY gen.py --tier $t --duration 90 --episodes 2 --seed 900 --scenes $val -o data/val
done
