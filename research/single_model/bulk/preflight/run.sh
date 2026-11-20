#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
B=research/single_model/bulk/preflight
W=research/results/single_model/bk_i2mb/solution.wasm
FX=research/results/single_model/preflight_c1_fx
export PYTHONPATH=/dev/shm/sebastian-vio/viobench OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
sha256sum $W > $B/sha.txt
args=""; for f in fast-102344457-00 fast-ProcTHOR-Train-151-09 fast-106878858_174886965-00 fastmid-ProcTHOR-Train-143-01 fastmid-108294897_176710602-01 fastmid-ProcTHOR-Train-158-07; do args="$args --fixture $FX/$f.npz"; done
PF="--prefix 1 --prefix 4 --prefix 8 --prefix 12 --prefix 24 --prefix 41 --prefix 120 --prefix 250 --prefix 600 --prefix 1199"
mkdir -p /data/backups/rganapa/Sebastian/tmp/bk_poison
TMPDIR=/data/backups/rganapa/Sebastian/tmp/bk_poison $PY -B research/check_future_poison.py --wasm $W $args $PF --output /data/backups/rganapa/Sebastian/tmp/bk_poison/out.json > $B/poison.log 2>$B/poison.err
for f in fast-102344457-00 fast-ProcTHOR-Train-151-09 fast-106878858_174886965-00 fastmid-ProcTHOR-Train-143-01 fastmid-108294897_176710602-01 fastmid-ProcTHOR-Train-158-07; do
  $PY -B research/single_model/final/preflight/reset_check.py $W $FX/$f.npz 400 /data/backups/rganapa/Sebastian/tmp/bk_poison/reset_$f.npy >> $B/reset.txt 2>>$B/reset.err
done
echo done > $B/done
