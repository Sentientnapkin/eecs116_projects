#!/bin/bash
# pcmp.sh <src.c> <tag> : build PROF variant, run 60 search flights, compare poses with baseline (fuelb13_prof) and print fuel summary
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/fuel_b13
P=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
python3 mkprof.py $1 p_$2.c 2>/dev/null
bash ../fuel/buildprof.sh p_$2.c p_$2.wasm -O3 $(cat defs.txt) $3
O=../../results/single_model/fuelb13_prof_$2; rm -rf $O
cd ../../..; $P -B research/single_model/fuel/prof_run.py research/single_model/fuel_b13/p_$2.wasm research/results/single_model/fuelb13_prof_$2 ${N:-60} 16 | grep -v done
cd research/single_model/fuel_b13
$P - <<PY
import numpy as np, glob, os
a='../../results/single_model/fuelb13_prof'; b='$O'
ne=0; n=0
for f in sorted(glob.glob(b+'/*.npz')):
    g=os.path.join(a,os.path.basename(f))
    if not os.path.exists(g): continue
    x=np.load(f)['pose']; y=np.load(g)['pose']; n+=1
    if x.shape!=y.shape or not np.array_equal(x.view(np.uint64),y.view(np.uint64)): ne+=1
print('pose bit-identical flights: %d / %d'%(n-ne,n))
PY
$P an.py $O | head -2
