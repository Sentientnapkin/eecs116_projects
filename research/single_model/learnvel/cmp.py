"""cmp.py POOL BASE ARM [nreps] : paired comparison per rep (BASE{,_r1,_r2} vs ARM{,_r1,_r2}); scene-bootstrap CI; tails >1/3/5/10; peak.
POOL in st2dev st2conf st1dev st1conf fdev fconf (fdev/fconf also read from NAME__fresh_pool.json filtered by fold; fold 4 never used)."""
import json, sys, numpy as np, os, hashlib
H = os.path.dirname(os.path.abspath(__file__))
pool, base, arm = sys.argv[1:4]; NR = int(sys.argv[4]) if len(sys.argv) > 4 else 3
TAGS = json.load(open(os.path.join(H, '../fresh/tags.json')))
def fold(e):
    t = TAGS[e]; return int(hashlib.sha256((t['catalog'] + ':' + t['scene']).encode()).hexdigest()[:8], 16) % 5
def load(n):
    f = f'{H}/tables/{n}__{pool}.json'
    if os.path.exists(f): rows = json.load(open(f))
    elif pool in ('fdev', 'fconf') and os.path.exists(f'{H}/tables/{n}__fresh_pool.json'): rows = json.load(open(f'{H}/tables/{n}__fresh_pool.json'))
    else: return None
    if pool in ('fdev', 'fconf'): rows = [r for r in rows if r['ep'] in TAGS and ((fold(r['ep']) <= 2) if pool == 'fdev' else (fold(r['ep']) == 3))]
    return {r['ep']: r for r in rows if r.get('ate_rmse') is not None}
rng = np.random.default_rng(0); out = []
for sb in ['', '_r1', '_r2'][:NR]:
    B, A = load(base + sb), load(arm + sb)
    if not B or not A: continue
    ks = sorted(set(B) & set(A)); b = np.array([B[k]['ate_rmse'] for k in ks]); a = np.array([A[k]['ate_rmse'] for k in ks])
    sc = np.array([k.split('-', 1)[1].rsplit('-', 1)[0] for k in ks]); us = np.unique(sc); idx = {s: np.where(sc == s)[0] for s in us}
    bs = [a[ii].mean() - b[ii].mean() for ii in (np.concatenate([idx[s] for s in rng.choice(us, len(us))]) for _ in range(2000))]
    out.append((a.mean(), b.mean(), [(a > t).sum() for t in (3, 5, 10)], [(b > t).sum() for t in (3, 5, 10)], max(A[k]['peak'] for k in ks)))
    print('%-4s n %d base %.4f arm %.4f d %+.4f [%+.4f,%+.4f] | >1 %d/%d >3 %d/%d >5 %d/%d >10 %d/%d | peak %.2f/%.2f' % (sb or 'r0', len(ks), b.mean(), a.mean(), a.mean() - b.mean(), *np.percentile(bs, [2.5, 97.5]),
          (b > 1).sum(), (a > 1).sum(), (b > 3).sum(), (a > 3).sum(), (b > 5).sum(), (a > 5).sum(), (b > 10).sum(), (a > 10).sum(), max(B[k]['peak'] for k in ks) / 1e6, max(A[k]['peak'] for k in ks) / 1e6))
if out: print('%s %s vs %s: mean over %d reps: base %.4f arm %.4f (%+.1f%%)' % (pool, arm, base, len(out), np.mean([o[1] for o in out]), np.mean([o[0] for o in out]), 100 * (np.mean([o[0] for o in out]) / np.mean([o[1] for o in out]) - 1)))
