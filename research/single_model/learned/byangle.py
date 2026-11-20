"""Error vs angle between the camera axis (body x) and the true velocity: does the net depend on 'faces its direction of travel'?"""
import sys, numpy as np
sys.path.insert(0, '.')
from evalnets import HEAD_MU, HEAD_SD
names = sys.argv[1:]
ps = [np.load(f'preds/{n}.npz') for n in names]
mu = np.mean([p['mu'][:, 0] for p in ps], 0); y = ps[0]['y'][:, 0]
sp = np.linalg.norm(y, axis=1)
ang = np.degrees(np.arccos(np.clip(y[:, 0] / (sp + 1e-9), -1, 1)))
m = sp > 0.5
print('anchors with speed>0.5:', m.sum(), ' frac moving backwards (angle>90):', (ang[m] > 90).mean().round(3))
print('| angle bin | n | net err | net ang err (deg) | heading err | zero err |'); print('|---|---|---|---|---|---|')
for lo, hi in ((0, 30), (30, 60), (60, 90), (90, 135), (135, 181)):
    k = m & (ang >= lo) & (ang < hi)
    e = np.linalg.norm(mu[k] - y[k], axis=1)
    c = (mu[k] * y[k]).sum(1) / (np.linalg.norm(mu[k], axis=1) * sp[k] + 1e-9)
    print(f'| {lo}-{hi} | {k.sum()} | {e.mean():.3f} | {np.degrees(np.arccos(np.clip(c,-1,1))).mean():.1f} | {np.linalg.norm(HEAD_MU - y[k], axis=1).mean():.3f} | {sp[k].mean():.3f} |')
