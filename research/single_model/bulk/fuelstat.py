import sys, glob, numpy as np
run = sys.argv[1]
fs = sorted(glob.glob(f'/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/{run}/eval/*/*/report/logs/*/fuel.npy'))
A = np.array([np.load(f) for f in fs if len(np.load(f)) == 1200])
print(run, 'flights', len(A), 'max peak %.2fM' % (A.max() / 1e6), 'median of per-flight peaks %.2fM' % (np.median(A.max(1)) / 1e6), 'median frame %.2fM p95 %.2fM' % (np.median(A) / 1e6, np.percentile(A, 95) / 1e6))
ph = [A[:, i::4].mean() / 1e6 for i in range(4)]; print(' mean by frame%4', np.round(ph, 2), ' top1% frames by phase', np.bincount((np.argwhere(A >= np.percentile(A, 99))[:, 1]) % 4, minlength=4))
w = np.argwhere(A == A.max())[0]; print(' worst flight idx', w[0], 'frame', w[1], 'phase', w[1] % 4)
print(' frames-before-100 max %.2fM; mean over flight of per-frame max after 100 %.2fM' % (A[:, :100].max() / 1e6, A[:, 100:].max(1).mean() / 1e6))
