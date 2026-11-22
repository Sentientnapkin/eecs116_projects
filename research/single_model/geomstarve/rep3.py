"""rep3.py ARM [BASE=hm40] [pools...]: 3-rep means (NAME, NAME_r1, NAME_r2) and per-rep paired deltas vs BASE reps"""
import json, sys, os, numpy as np
def load(n, p):
    for d in ('tables', '../servertail/tables', '../filtcons/tables'):
        f = f'{d}/{n}__{p}.json'
        if os.path.exists(f): return {r['ep']: r['ate_rmse'] for r in json.load(open(f))}, max(r['peak'] for r in json.load(open(f)))
    return None, None
arm = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else 'hm40'; pools = sys.argv[3:] or ['st2dev', 'st2conf']
for p in pools:
    out = []
    for s in ('', '_r1', '_r2'):
        A, pa = load(arm + s, p); B, pb = load(base + s, p)
        if A is None or B is None: continue
        ks = sorted(set(A) & set(B)); a = np.array([A[k] for k in ks]); b = np.array([B[k] for k in ks])
        out.append((b.mean(), a.mean(), (a > 3).sum(), (b > 3).sum(), (a > 5).sum(), pa))
    if out:
        o = np.array(out)
        print('%-8s %-8s reps %d base %.4f arm %.4f (%+.1f%%) per-rep d %s | >3 arm %s base %s | >5 arm %s | peak %.2f M' % (p, arm, len(o), o[:, 0].mean(), o[:, 1].mean(), 100 * (o[:, 1].mean() / o[:, 0].mean() - 1),
              ' '.join('%+.3f' % (x[1] - x[0]) for x in o), [int(x) for x in o[:, 2]], [int(x) for x in o[:, 3]], [int(x) for x in o[:, 4]], o[:, 5].max() / 1e6))
