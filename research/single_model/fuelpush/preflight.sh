#!/bin/bash
# preflight.sh <wasm> <outdir> : sha, imports, ABI check, poison/causality prefixes (18 fixtures x prefixes), reset 8 fixtures
cd /data/backups/rganapa/Sebastian/eecs116_projects
W=$1; P=$2; mkdir -p $P
FX=research/results/single_model/preflight_c1_fx
export PYTHONPATH=/dev/shm/sebastian-vio/viobench OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
T=/data/backups/rganapa/Sebastian/tmp/fppf_$(basename $P); mkdir -p $T; export TMPDIR=$T
sha256sum $W > $P/sha256.txt
$PY -B -c "
import wasmtime
m=wasmtime.Module(wasmtime.Engine(),open('$W','rb').read())
print('imports:',[(i.module,i.name) for i in m.imports],'exports:',[e.name for e in m.exports])" > $P/imports.txt 2>&1
$PY -B -c "
from viobench.tools.runner.check import check
import sys; sys.exit(check('$W', frames=5))" > $P/abi_check.txt 2>&1; echo "exit $?" >> $P/abi_check.txt
mapfile -t L < research/single_model/final/preflight_c1_fbh/fixtures_list.txt
PF=""; for p in 1 2 4 5 6 7 8 9 10 11 12 13 14 15 16 20 24 29 30 31 40 41 60 61 62 63 64 65 66 70 80 99 100 101 102 103 104 105 120 600 1199; do PF="$PF --prefix $p"; done
for g in 0 1 2; do
  args=""; for k in 0 1 2 3 4 5; do args="$args --fixture $FX/${L[$((g*6+k))]}.npz"; done
  ( $PY -B research/check_future_poison.py --wasm $W $args $PF --output $P/poison_$g.json > $P/poison_$g.log 2> $P/poison_$g.err ) &
done
wait
: > $P/reset.txt
sed "s#^W = Path(.*)#W = Path('$W')#; s#b16_reset_logs#fp_reset_logs#g" research/single_model/tailcap/preflight_b16/reset_check.py > $T/reset_check.py
$PY -B $T/reset_check.py > $P/reset.txt 2> $P/reset.err
echo done > $P/done
