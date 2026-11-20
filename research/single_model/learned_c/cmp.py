"""Compare builds by start-angle bin. usage: cmp.py s171|f3 ref name1 name2 ... ; ref/names are table names (tables/<kind>_<name>.json)"""
import json, sys
import numpy as np
kind, ref, names = sys.argv[1], sys.argv[2], sys.argv[3:]
F = json.load(open('feats.json'))
def load(n): return {r['episode']: r['ate'] for r in json.load(open(f'tables/{kind}_{n}.json')) if r['ate'] is not None}
T = {n: load(n) for n in [ref] + names}
eps = sorted(set.intersection(*[set(t) for t in T.values()]))
ang = np.array([F[e]['angle'] if F[e]['angle'] is not None else np.nan for e in eps]); spd = np.array([F[e]['speed0'] for e in eps])
mid = np.array([F[e]['start'] == 'mid' for e in eps])
scene = np.array([F[e]['catalog'] + ':' + F[e]['scene'] for e in eps])
A = {n: np.array([T[n][e] for e in eps]) for n in T}
def boot(d, sc, n=3000, seed=1):
    rng = np.random.default_rng(seed); u, inv = np.unique(sc, return_inverse=True)
    s = np.bincount(inv, weights=d); k = np.bincount(inv); idx = rng.integers(0, len(u), (n, len(u)))
    return np.percentile(s[idx].sum(1) / k[idx].sum(1), [2.5, 97.5])
bins = [('all', np.ones(len(eps), bool)), ('static', ~mid), ('mid', mid), ('mid v>0.3', mid & (spd > 0.3))] + [('v>1.8', mid & (spd > 1.8)), ('0.3<v<=1.8', mid & (spd > 0.3) & (spd <= 1.8)), ('v<=0.3 mid', mid & (spd <= 0.3))] + [(f'ang {lo}-{hi}', mid & (spd > 0.3) & (ang >= lo) & (ang < hi)) for lo, hi in [(0, 45), (45, 90), (90, 135), (135, 181)]]
print(f'{kind}: n={len(eps)}  ref={ref}')
for lab, m in bins:
    if m.sum() == 0: continue
    s = f'{lab:12s} n={m.sum():3d} ' + ' | '.join(f'{n}: {A[n][m].mean():.3f} (>3:{(A[n][m] > 3).sum()}, >5:{(A[n][m] > 5).sum()}, >10:{(A[n][m] > 10).sum()})' for n in T)
    print(s)
for n in names:
    for lab, m in bins[:3]:
        d = A[n][m] - A[ref][m]; lo, hi = boot(d, scene[m]); print(f'  {n} - {ref} {lab:7s} {d.mean():+.3f} [{lo:+.3f}, {hi:+.3f}]')
    d = A[n] - A[ref]; w = np.argsort(-d)[:5]
    print('  worst vs ref:', ', '.join(f'{eps[i]} {A[ref][i]:.2f}->{A[n][i]:.2f} ang {ang[i]:.0f} spd {spd[i]:.2f}' for i in w))
