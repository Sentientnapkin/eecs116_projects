"""usage: python -B cmpf.py ref arm [arm...]   (names in bulk/tables/<n>.json, or 'B6' = fresh/table_fe2_fbh.json). Dev folds 0-2 / confirm 3-4 of the fresh set."""
import sys, json, hashlib
import numpy as np
H = '/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/'
def load(n):
    p = H + 'fresh/table_fe2_fbh.json' if n == 'B6' else H + f'bulk/tables/{n}.json'
    return {r['episode']: r for r in json.load(open(p))}
def fold(r): return int(hashlib.sha256(f"{r['catalog']}:{r['scene']}".encode()).hexdigest()[:8], 16) % 5
def boot(d, sc, n=3000, seed=1):
    rng = np.random.default_rng(seed); u, inv = np.unique(sc, return_inverse=True)
    s = np.bincount(inv, weights=d); k = np.bincount(inv); idx = rng.integers(0, len(u), (n, len(u)))
    b = s[idx].sum(1) / k[idx].sum(1); return np.percentile(b, [2.5, 97.5])
ref = load(sys.argv[1]); eps = sorted(ref)
fl = np.array([fold(ref[e]) for e in eps]); st = np.array([ref[e]['start'] for e in eps]); sc = np.array([ref[e]['catalog'] + ref[e]['scene'] for e in eps])
def line(lab, a, r, m):
    d = a[m] - r[m]; lo, hi = boot(d, sc[m])
    return f'{lab:8s} n={m.sum():3d} ref {r[m].mean():.3f}/{np.median(r[m]):.3f} arm {a[m].mean():.3f}/{np.median(a[m]):.3f} d {d.mean():+.3f} [{lo:+.3f},{hi:+.3f}]'
R = np.array([ref[e]['ate'] for e in eps])
for n in sys.argv[2:]:
    arm = load(n); A = np.array([arm[e]['ate'] if arm[e]['ate'] is not None else np.nan for e in eps]); pf = np.nanmax([arm[e]['peak_fuel'] or 0 for e in eps]) / 1e6
    print(f'== {n}: all mean {np.nanmean(A):.3f} median {np.nanmedian(A):.3f} p25/p75 {np.nanpercentile(A,25):.3f}/{np.nanpercentile(A,75):.3f} >3/5/10 {(A>3).sum()}/{(A>5).sum()}/{(A>10).sum()} peak fuel {pf:.1f}M  (ref {R.mean():.3f}/{np.median(R):.3f}, >3/5/10 {(R>3).sum()}/{(R>5).sum()}/{(R>10).sum()})')
    for lab, m in [('all', fl >= 0), ('dev', fl <= 2), ('confirm', fl >= 3), ('dev stat', (fl <= 2) & (st == 'static')), ('dev mid', (fl <= 2) & (st == 'mid')), ('conf st', (fl >= 3) & (st == 'static')), ('conf mid', (fl >= 3) & (st == 'mid'))]:
        print('  ' + line(lab, A, R, m))
