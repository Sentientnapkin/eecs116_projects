import json, os, numpy as np
H = os.path.dirname(os.path.abspath(__file__)) + '/'
C = [c for c in ('base', 'gate', 'gatec1') if os.path.exists(H + f'table_{c}.json')]
tab = {c: {r['episode']: r for r in json.load(open(H + f'table_{c}.json'))} for c in C}
eps = sorted(tab[C[0]])
A = {c: np.array([tab[c][e]['ate'] if tab[c][e]['ate'] is not None else np.nan for e in eps], float) for c in C}
t = json.load(open(H + 'tags.json')); start = np.array([t[e]['start'] for e in eps]); scene = np.array([t[e]['catalog'] + ':' + t[e]['scene'] for e in eps])
out = []; P = lambda *a: out.append(' '.join(str(x) for x in a))
def st(v): return f'n={len(v)} mean {np.nanmean(v):.3f} med {np.nanmedian(v):.2f} p90 {np.nanpercentile(v, 90):.2f} p95 {np.nanpercentile(v, 95):.2f} max {np.nanmax(v):.2f} | >3: {(v > 3).sum()} >5: {(v > 5).sum()} >10: {(v > 10).sum()} | nan {np.isnan(v).sum()}'
def boot(d, n=4000):
    rng = np.random.default_rng(1); u, inv = np.unique(scene[m_], return_inverse=True)
    s = np.bincount(inv, weights=d); k = np.bincount(inv); idx = rng.integers(0, len(u), (n, len(u)))
    return d.mean(), *np.percentile(s[idx].sum(1) / k[idx].sum(1), [2.5, 97.5])
for lab, m in (('all', np.ones(len(eps), bool)), ('static', start == 'static'), ('mid', start == 'mid')):
    P(f'## {lab}'); P('```')
    for c in C: P(f'{c:7s}', st(A[c][m]))
    P('```')
P('## Paired scene-bootstrap (new - ref), 95% CI'); P('```')
for a, b in (('gate', 'base'), ('gatec1', 'base'), ('gatec1', 'gate')):
    if a in C and b in C:
        for lab, m in (('all', np.ones(len(eps), bool)), ('static', start == 'static'), ('mid', start == 'mid')):
            m_ = m; d, lo, hi = boot(A[a][m] - A[b][m]); P(f'{a:7s}-{b:5s} {lab:6s} {d:+.3f} [{lo:+.3f}, {hi:+.3f}]  worse>1m {(A[a][m]-A[b][m] > 1).sum()} better>1m {(A[a][m]-A[b][m] < -1).sum()}')
P('```')
open(H + 'RESULTS.md', 'w').write('# Holdout scores (one-shot)\n' + '\n'.join(out) + '\n'); print('\n'.join(out))
