#!/bin/bash
# prof.sh SRC TAG "DEFS(-DX=1 ...)" [N=60] [REF_TAG] : profile build (host marks), N search flights, phase table; optional pose bit-compare vs tier1m prof REF_TAG
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/audit
P=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
mkdir -p prof; python3 mkprof.py $1 prof/p_$2.c 2>/dev/null
bash ../fuel/buildprof.sh prof/p_$2.c prof/p_$2.wasm -O3 $3; [ -f prof/p_$2.wasm ] || exit 1
O=../../results/single_model/aud_prof_$2; rm -rf $O
cd ../../..; $P -B research/single_model/fuel/prof_run.py research/single_model/audit/prof/p_$2.wasm research/results/single_model/aud_prof_$2 ${4:-60} ${W:-16} | grep -v done
cd research/single_model/audit
if [ -n "$5" ]; then $P - <<PY
import numpy as np, glob, os
a='../../results/single_model/aud_prof_$5'; b='$O'; ne=0; n=0
for f in sorted(glob.glob(b+'/*.npz')):
    g=os.path.join(a,os.path.basename(f))
    if not os.path.exists(g): continue
    x=np.load(f)['pose']; y=np.load(g)['pose']; n+=1
    if x.shape!=y.shape or not np.array_equal(x.view(np.uint64),y.view(np.uint64)): ne+=1
print('pose bit-identical flights vs $5: %d / %d'%(n-ne,n))
PY
fi
$P an.py $O > prof/an_$2.txt; head -1 prof/an_$2.txt
