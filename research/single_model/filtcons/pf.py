import json, sys, numpy as np
a, b = sys.argv[1], sys.argv[2]; pool = sys.argv[3] if len(sys.argv) > 3 else 'st2dev'
def L(n): return {r['ep']: r for r in json.load(open(f'tables/{n}__{pool}.json'))}
B = {}
for r in ['', '_r1', '_r2']:
    try:
        for e, x in L(b + r).items(): B.setdefault(e, []).append(x['ate_rmse'])
    except FileNotFoundError: pass
A = L(a); ks = sorted(A, key=lambda e: -np.mean(B[e]))
for e in ks[:15]: print('%-40s base %s arm %.2f' % (e[:40], ' '.join('%.2f' % v for v in B[e]), A[e]['ate_rmse']))
bm = np.array([np.mean(B[e]) for e in ks]); am = np.array([A[e]['ate_rmse'] for e in ks])
print('mean base(3rep) %.4f arm %.4f | top30 %.3f -> %.3f | rest %.3f -> %.3f' % (bm.mean(), am.mean(), bm[:30].mean(), am[:30].mean(), bm[30:].mean(), am[30:].mean()))
