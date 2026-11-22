"""filter velocity error decomposition (along / perp to truth) on st2dev, by filter error class; twist vs truth per frame"""
import sys, glob, json, numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
run, pool = sys.argv[1], sys.argv[2]
A = []
for tw in sorted(glob.glob(f'{run}/*/*/report/logs/*/twist.txt')):
    ep = tw.split('/')[-5]; t = np.loadtxt(tw); S = np.asarray(read_episode(f'{pool}/{ep}.zip', frames='none').ground_truth_state())
    if len(t) != len(S): continue
    ve, vt = t[:, 1:4], S[:, 7:10]; sp = np.linalg.norm(vt, axis=1); e = np.linalg.norm(ve - vt, axis=1)
    ok = sp > 0.5; al = (ve * vt).sum(1) / np.maximum(sp, 1e-6) ** 2
    perp = np.linalg.norm(ve - al[:, None] * vt, axis=1)
    A.append(np.stack([e, sp, al, perp], 1)[ok])
A = np.concatenate(A); e, sp, al, perp = A.T
for lo, hi in [(0, .3), (.3, .5), (.5, 1), (1, 9)]:
    m = (e >= lo) & (e < hi); print('filter err %.1f-%.1f n %6d along-scale mean %.2f median %.2f | |scale-1|*spd %.2f  perp %.2f  spd %.2f' % (lo, hi, m.sum(), al[m].mean(), np.median(al[m]), (np.abs(al[m] - 1) * sp[m]).mean(), perp[m].mean(), sp[m].mean()))
