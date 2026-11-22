"""cmp2.py BASE ARM POOL [ref_dir]: paired per-flight comparison (tables NAME__POOL.json; base may be from servertail tables)"""
import json, sys, os, numpy as np
def load(n, p):
    for d in ('tables', '../servertail/tables', '../filtcons/tables'):
        f = f'{d}/{n}__{p}.json'
        if os.path.exists(f): return {r['ep']: r for r in json.load(open(f))}
    raise SystemExit('missing ' + n)
b, a, p = sys.argv[1:4]
SUB = os.environ.get('SUB', 'all')
if p.startswith('fresh'):
    import hashlib; T = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../fresh/tags.json')))
    fold = lambda e: int(hashlib.sha256((T[e]['catalog'] + ':' + T[e]['scene']).encode()).hexdigest()[:8], 16) % 5
    keep = lambda e: fold(e) != 4 and (SUB == 'all' or (SUB == 'dev' and fold(e) <= 2) or (SUB == 'conf' and fold(e) == 3))
else: keep = lambda e: True
pa = p
def load2(n):
    try: return load(n, pa)
    except SystemExit:
        if pa == 'fresh03': return load(n, 'fresh_pool')
        raise
B, A = load2(b), load2(a); ks = sorted(k for k in set(B) & set(A) if keep(k))
x = np.array([B[k]['ate_rmse'] for k in ks]); y = np.array([A[k]['ate_rmse'] for k in ks])
sc = np.array([k.split('-', 1)[1].rsplit('-', 1)[0] for k in ks]); us = np.unique(sc); idx = {s: np.where(sc == s)[0] for s in us}
rng = np.random.default_rng(0); bs = [(y[ii] - x[ii]).mean() for ii in (np.concatenate([idx[s] for s in rng.choice(us, len(us))]) for _ in range(2000))]
print('%s vs %s %s n %d base %.4f arm %.4f d %+.4f [%+.4f,%+.4f] >1 %d/%d >3 %d/%d >5 %d/%d peak %.2f/%.2f' % (a, b, p, len(ks), x.mean(), y.mean(), y.mean() - x.mean(), *np.percentile(bs, [2.5, 97.5]),
      (x > 1).sum(), (y > 1).sum(), (x > 3).sum(), (y > 3).sum(), (x > 5).sum(), (y > 5).sum(), max(B[k]['peak'] for k in ks) / 1e6, max(A[k]['peak'] for k in ks) / 1e6))
if len(sys.argv) > 4:
    o = np.argsort(-(np.abs(y - x)))
    for i in o[:int(sys.argv[4])]: print('  %-38s %.2f -> %.2f' % (ks[i], x[i], y[i]))
