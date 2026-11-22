B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/pq.sh
bash $B build mt0 FAST_KLT=1 DETECT_MAX_CELLS=6 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 MAX_CLONES=3 ITER_UPD=1 OLD_EARLY=1
bash $B build mt1 FAST_KLT=1 DETECT_MAX_CELLS=6 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 MAX_CLONES=3 ITER_UPD=1 OLD_EARLY=1 MEMCPY_TEST=1
bash $B run mt0 & bash $B run mt1 & wait
source ~/.venv/bin/activate; python - <<'PY'
import numpy as np, glob
for n in ('mt0','mt1'):
    seg = np.concatenate([np.load(f)['seg'] for f in sorted(glob.glob('/home/alexa/prof/%s/*.npz' % n))])
    print(n, 'entry(seg0) mean', seg[:,0].mean(), 'total mean', seg.sum(1).mean())
PY
