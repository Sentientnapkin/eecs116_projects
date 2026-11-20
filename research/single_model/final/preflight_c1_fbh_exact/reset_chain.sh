#!/bin/bash
cd /data/backups/rganapa/Sebastian/eecs116_projects
P=research/single_model/final/preflight_c1_fbh_exact
FX=research/results/single_model/preflight_c1_fx
W=$P/gp_msckf_startup_gate_c1_fbh_exact_verified.wasm
: > $P/reset_check.txt
for f in $(grep -v '^fastmid' $P/fixtures_list.txt | head -5) $(grep '^fastmid' $P/fixtures_list.txt | head -3); do
 mkdir -p /data/backups/rganapa/Sebastian/tmp/pfx_reset
 TMPDIR=/data/backups/rganapa/Sebastian/tmp/pfx_reset OPENBLAS_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python -B research/single_model/final/preflight/reset_check.py $W $FX/$f.npz 600 /data/backups/rganapa/Sebastian/tmp/pfx_reset/$f.json >> $P/reset_check.txt 2>>$P/reset_check.err
done
echo done > $P/reset.done
