"""cmpd.py A.json B.json ... : per-distance-bin mean ATE and tails, paired over common episodes"""
import json, sys, numpy as np
T = [{r['ep']: r for r in json.load(open(f))} for f in sys.argv[1:]]
ks = sorted(set.intersection(*[set(t) for t in T]))
d = np.array([T[0][k]['distance_travelled'] for k in ks])
print('n', len(ks))
for f, t in zip(sys.argv[1:], T):
    a = np.array([t[k]['ate_rmse'] for k in ks]); pk = max(t[k]['peak'] for k in ks)
    bins = ' '.join('%.3f' % a[(d >= lo) & (d < hi)].mean() for lo, hi in [(0, 45), (45, 55), (55, 200)])
    print('%-28s mean %.4f | <45/45-55/>55 %s | >1 %d >3 %d >5 %d | peak %.2f M' % (f.split('/')[-1][:28], a.mean(), bins, (a > 1).sum(), (a > 3).sum(), (a > 5).sum(), pk / 1e6))
