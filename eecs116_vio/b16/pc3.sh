B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/pq.sh
bash $B build e4 FAST_KLT=1 MAX_CLONES=5 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 VIS_SPLIT=1 MAP_SIMD=1 FLOW_PRED=1.0 HALF_RES=1 LC_SLICE=2 PRIOR_ALT=1 UPD_ROWCAP=12 GRAY_G=1 DETECT_MAX_CELLS=3 MAP_TRY=2 LC_SLICE=1 LC_GB=4 LC_PREP_PARTS=4 LC_C0R=8 LC_C1R=6 PREP_FAST=1
bash $B run e4
source ~/.venv/bin/activate
python - <<'PY'
import numpy as np, glob
z=[np.load(f) for f in sorted(glob.glob('/home/alexa/prof/e4/*.npz'))]
t=np.array([a['seg'].sum(1)[:40] for a in z])
print('first 40 frames, max over flights (M):', ' '.join('%.1f' % x for x in t.max(0)/1e6))
lc=np.array([a['seg'][:40, 3] + a['seg'][:40, 20] + a['seg'][:40, 27] for a in z]).max(0)
print('net part (M):', ' '.join('%.1f' % x for x in lc/1e6))
PY
