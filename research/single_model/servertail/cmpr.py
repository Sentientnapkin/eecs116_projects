"""cmpr.py POOL BASE ARM : 3-rep paired comparison (BASE{,_r1,_r2} vs ARM{,_r1,_r2}); scene-bootstrap CI of mean diff; tails; peak"""
import json, sys, numpy as np, os
pool, base, arm = sys.argv[1:4]; SUB = sys.argv[4] if len(sys.argv) > 4 else 'all'
import hashlib
TAGS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../fresh/tags.json')))
def fold(e):
    t = TAGS[e]; return int(hashlib.sha256((t['catalog'] + ':' + t['scene']).encode()).hexdigest()[:8], 16) % 5
def keep(e):
    if pool != 'fresh_pool': return True
    f = fold(e)
    return f != 4 and (SUB == 'all' or (SUB == 'dev' and f <= 2) or (SUB == 'conf' and f == 3))
def load(n):
    f = f'tables/{n}__{pool}.json'
    return {r['ep']: r for r in json.load(open(f))} if os.path.exists(f) else None
reps = [('', ''), ('_r1', '_r1'), ('_r2', '_r2')]
rng = np.random.default_rng(0); out = []
for sb, sa in reps:
    B, A = load(base + sb), load(arm + sa)
    if not B or not A: continue
    ks = sorted(k for k in set(B) & set(A) if keep(k)); b = np.array([B[k]['ate_rmse'] for k in ks]); a = np.array([A[k]['ate_rmse'] for k in ks])
    sc = np.array([k.split('-', 1)[1].rsplit('-', 1)[0] for k in ks]); us = np.unique(sc); idx = {s: np.where(sc == s)[0] for s in us}
    bs = []
    for _ in range(2000):
        ii = np.concatenate([idx[s] for s in rng.choice(us, len(us))]); bs.append(a[ii].mean() - b[ii].mean())
    out.append((a.mean(), b.mean()))
    print('%-4s n %d base %.4f arm %.4f d %+.4f [%+.4f,%+.4f] | >1 %d/%d >3 %d/%d >5 %d/%d | peak %.2f/%.2f' % (sb or 'r0', len(ks), b.mean(), a.mean(), a.mean() - b.mean(), *np.percentile(bs, [2.5, 97.5]),
          (b > 1).sum(), (a > 1).sum(), (b > 3).sum(), (a > 3).sum(), (b > 5).sum(), (a > 5).sum(), max(B[k]['peak'] for k in ks) / 1e6, max(A[k]['peak'] for k in ks) / 1e6))
if out: print('mean over reps: base %.4f arm %.4f (%+.1f%%)' % (np.mean([o[1] for o in out]), np.mean([o[0] for o in out]), 100 * (np.mean([o[0] for o in out]) / np.mean([o[1] for o in out]) - 1)))
