#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
P=research/single_model/tailcap/preflight_b15
FX=research/results/single_model/preflight_c1_fx
W=research/single_model/tailcap/gp_msckf_startup_b15_pv25.wasm
mapfile -t LST < research/single_model/final/preflight_c1_fbh/fixtures_list.txt
PF="--prefix 1 --prefix 2 --prefix 4 --prefix 5 --prefix 6 --prefix 8 --prefix 9 --prefix 10 --prefix 11 --prefix 12 --prefix 29 --prefix 30 --prefix 31 --prefix 40 --prefix 41 --prefix 60 --prefix 120 --prefix 600 --prefix 1199"
for g in 0 1 2; do
  args=""; for k in 0 1 2 3 4 5; do args="$args --fixture $FX/${LST[$((g*6+k))]}.npz"; done
  mkdir -p /data/backups/rganapa/Sebastian/tmp/b15_poison_$g
  ( TMPDIR=/data/backups/rganapa/Sebastian/tmp/b15_poison_$g PYTHONPATH=/dev/shm/sebastian-vio/viobench OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python -B research/check_future_poison.py --wasm $W $args $PF --output /data/backups/rganapa/Sebastian/tmp/b15_poison_$g/out.json > $P/poison_g$g.log 2>$P/poison_g$g.err ) &
done
wait
echo done > $P/poison.done
