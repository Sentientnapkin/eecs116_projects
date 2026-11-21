#!/bin/bash
# usage: run.sh <wasm> ; outputs in bulk/preflight_final/
cd /data/backups/rganapa/Sebastian/eecs116_projects
W=$1
P=research/single_model/bulk/preflight_final
FX=research/results/single_model/preflight_c1_fx
export PYTHONPATH=/dev/shm/sebastian-vio/viobench OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
mkdir -p /data/backups/rganapa/Sebastian/tmp/bkpf; export TMPDIR=/data/backups/rganapa/Sebastian/tmp/bkpf
sha256sum $W > $P/sha256.txt
$PY -B -c "
import sys,wasmtime
m=wasmtime.Module(wasmtime.Engine(),open('$W','rb').read())
print('imports:',[(i.module,i.name) for i in m.imports],'exports:',[e.name for e in m.exports])" > $P/imports.txt 2>&1
$PY -B -c "
from viobench.tools.runner.check import check
import sys; sys.exit(check('$W', frames=5))" > $P/abi_check.txt 2>&1; echo "exit $?" >> $P/abi_check.txt
mapfile -t L < research/single_model/final/preflight_c1_fbh/fixtures_list.txt
PF=""; for p in 1 2 4 5 6 8 9 10 11 12 20 21 23 24 28 40 41 50 99 100 101 103 104 105 120 600 1199; do PF="$PF --prefix $p"; done
: > $P/poison_all.log
for g in 0 1 2; do
  args=""; for k in 0 1 2 3 4 5; do args="$args --fixture $FX/${L[$((g*6+k))]}.npz"; done
  $PY -B research/check_future_poison.py --wasm $W $args $PF --output $P/poison_$g.json >> $P/poison_all.log 2>>$P/poison.err
done
: > $P/reset.txt
for f in "${L[@]:0:8}"; do $PY -B research/single_model/final/preflight/reset_check.py $W $FX/$f.npz 600 /data/backups/rganapa/Sebastian/tmp/bkpf/reset_$f.json >> $P/reset.txt 2>>$P/reset.err; done
echo done > $P/done
