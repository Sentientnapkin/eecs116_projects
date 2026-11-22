"""pooled.py ARM [BASE=hm40] [POOLS=st2dev,st3]: per-rep pooled mean, % vs base, tails (summed over reps), scene-bootstrap CI of the 3-rep mean diff"""
import json, sys, os, numpy as np
arm = sys.argv[1]; base = sys.argv[2] if len(sys.argv) > 2 else 'hm40'; pools = (sys.argv[3] if len(sys.argv) > 3 else 'st2dev,st3').split(',')
H = os.path.dirname(os.path.abspath(__file__))
def L(n, p):
    f = f'{H}/tables/{n}__{p}.json'
    return {r['ep']: (r['ate_rmse'], r['peak']) for r in json.load(open(f))} if os.path.exists(f) else None
A, B = {}, {}
for s in ['', '_r1', '_r2']:
    for p in pools:
        a, b = L(arm + s, p), L(base + s, p)
        if a and b:
            for k in set(a) & set(b): A.setdefault(k, []).append(a[k]); B.setdefault(k, []).append(b[k])
ks = sorted(k for k in A if len(A[k]) == len(B[k]) and len(A[k]) > 0); nr = min(len(A[k]) for k in ks)
a = np.array([[x[0] for x in A[k][:nr]] for k in ks]); b = np.array([[x[0] for x in B[k][:nr]] for k in ks])
sc = np.array([k.split('-', 1)[1].rsplit('-', 1)[0] for k in ks]); us = np.unique(sc); idx = {s: np.where(sc == s)[0] for s in us}; rng = np.random.default_rng(0)
d = a.mean(1) - b.mean(1); bs = [d[np.concatenate([idx[s] for s in rng.choice(us, len(us))])].mean() for _ in range(2000)]
print('%-12s n %d reps %d base %.4f arm %.4f (%+.1f%%) d CI [%+.4f,%+.4f] | per-rep arm %s | >3 %d/%d >5 %d/%d >10 %d/%d | peak %.2f/%.2f' % (arm, len(ks), nr, b.mean(), a.mean(), 100 * (a.mean() / b.mean() - 1), *np.percentile(bs, [2.5, 97.5]),
      ' '.join('%.3f' % x for x in a.mean(0)), (b > 3).sum(), (a > 3).sum(), (b > 5).sum(), (a > 5).sum(), (b > 10).sum(), (a > 10).sum(),
      max(x[1] for k in ks for x in B[k]) / 1e6, max(x[1] for k in ks for x in A[k]) / 1e6))
