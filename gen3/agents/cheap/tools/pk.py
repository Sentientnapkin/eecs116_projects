import glob,sys,numpy as np
fl=sys.argv[1]
for n in sys.argv[2:]:
    fs=sorted(glob.glob(f'/data/backups/rganapa/Sebastian/gen3/evals/{n}/*/*/{fl}/report/logs/*/fuel.npy'))
    a=np.load(fs[-1]); print(n, int(a.max()), a.argmax(), int(np.percentile(a,95)), int(a.mean()), (a[:80:4]/1e3).astype(int))
