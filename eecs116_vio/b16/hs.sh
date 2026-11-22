B=/mnt/c/Users/alexa/Projects/eecs116_vio/b16/pq.sh
bash $B build h4 FAST_KLT=1 DETECT_MAX_CELLS=6 MAP_SPREAD=1 LC_SPREAD=5 LC_PREP_SPLIT=1 MAX_UPDATE_FEATURES=8 ITER_MAXF=6 MAP_TRY=3 VIS_SPLIT=1 MAP_SIMD=1 MAX_CLONES=3 ITER_UPD=1 OLD_EARLY=1 HALF_RES=1 LC_SLICE=1
bash $B run h4
source ~/.venv/bin/activate; python /mnt/c/Users/alexa/Projects/eecs116_vio/b16/prof_pk2.py ~/prof/h4 1.2 | head -3
python - <<'PY'
import numpy as np, glob
segs=[np.load(f)["seg"] for f in sorted(glob.glob("/home/alexa/prof/h4/*.npz"))]
for ph in range(4):
    t=np.concatenate([s.sum(1)[60:][(np.arange(60,len(s))%4)==ph] for s in segs])
    print("mod4", ph, "median %.2f p90 %.2f p99 %.2f max %.2f" % (np.median(t)/1e6, np.percentile(t,90)/1e6, np.percentile(t,99)/1e6, t.max()/1e6))
t=np.concatenate([s.sum(1)[:60] for s in segs]); print("first 60 frames max %.2f p90 %.2f" % (t.max()/1e6, np.percentile(t,90)/1e6))
PY
