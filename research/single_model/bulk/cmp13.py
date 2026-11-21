"""usage: cmp13.py ref_prefix arm_prefix [reps=3] : e.g. bk_b10r bk_b13r. s171 search/val (visible flights), fold-3 unselected, fresh confirm (folds 3-4), per-replicate and replicate-mean, tails, persistence."""
import sys, json, hashlib
import numpy as np
from pathlib import Path
H = Path('/data/backups/rganapa/Sebastian/eecs116_projects/research')
ref, arm = sys.argv[1], sys.argv[2]; reps = int(sys.argv[3]) if len(sys.argv) > 3 else 3
def fold(r): return int(hashlib.sha256(f"{r['catalog']}:{r['scene']}".encode()).hexdigest()[:8], 16) % 5
def s171(n):
    d = json.loads((H / f'results/single_model/{n}/report.json').read_text())['rows_visible']
    return {r['e']: (r['new'], r['fold'], r['scene'], r['start']) for r in d}
def f3(n): return {r['episode']: r['ate'] for r in json.load(open(H / f'single_model/bulk/tables/{n}.f3.json'))}
def fresh(n): return {r['episode']: r for r in json.load(open(H / f'single_model/bulk/tables/{n}.json'))}
def stats(v): v = np.array(v); return f'{v.mean():.3f}/{np.median(v):.2f} >3/5/10 {(v>3).sum()}/{(v>5).sum()}/{(v>10).sum()}'
def boot(d, sc, n=3000):
    rng = np.random.default_rng(1); u, inv = np.unique(sc, return_inverse=True); s = np.bincount(inv, weights=d); k = np.bincount(inv); idx = rng.integers(0, len(u), (n, len(u)))
    return np.percentile(s[idx].sum(1) / k[idx].sum(1), [2.5, 97.5])
for k in range(reps):
    pass
names = lambda p: [p[:-1]] if p.endswith('!') else [f'{p}{k}' for k in range(reps)]
# s171
for lab, folds in (('s171 search', (0, 1, 2)), ('s171 val', (3,))):
    R = [s171(n) for n in names(ref)]; A = [s171(n) for n in names(arm)]
    ks = [e for e in R[0] if R[0][e][1] in folds]
    print(lab, 'n', len(ks), '| ref per-rep', [round(np.mean([r[e][0] for e in ks]), 3) for r in R], 'arm per-rep', [round(np.mean([r[e][0] for e in ks]), 3) for r in A],
          '| repmean ref %.3f arm %.3f' % (np.mean([np.mean([r[e][0] for r in R]) for e in ks]), np.mean([np.mean([r[e][0] for r in A]) for e in ks])))
    x = np.array([np.mean([r[e][0] for r in R]) for e in ks]); y = np.array([np.mean([r[e][0] for r in A]) for e in ks]); sc = [R[0][e][2] for e in ks]
    print('   paired d %+.3f [%+.3f,%+.3f]' % ((y - x).mean(), *boot(y - x, sc)), ' per-rep >3:', [int(sum(r[e][0] > 3 for e in ks)) for r in R], [int(sum(r[e][0] > 3 for e in ks)) for r in A])
# f3
R = [f3(n) for n in names(ref)]; A = [f3(n) for n in names(arm)]; ks = sorted(R[0])
print('f3 n', len(ks), '| per-rep ref', [round(np.mean(list(r.values())), 3) for r in R], 'arm', [round(np.mean(list(r.values())), 3) for r in A])
x = np.array([np.mean([r[e] for r in R]) for e in ks]); y = np.array([np.mean([r[e] for r in A]) for e in ks])
print('   repmean ref %.3f arm %.3f | tails per-rep ref >3' % (x.mean(), y.mean()), [int(sum(v > 3 for v in r.values())) for r in R], 'arm', [int(sum(v > 3 for v in r.values())) for r in A])
# fresh confirm
R = [fresh(n) for n in names(ref)]; A = [fresh(n) for n in names(arm)]
eps = [e for e in R[0] if fold(R[0][e]) >= 3]; sc = [R[0][e]['catalog'] + R[0][e]['scene'] for e in eps]
for lab, m in (('confirm all', [True] * len(eps)), ('confirm static', [R[0][e]['start'] == 'static' for e in eps]), ('confirm mid', [R[0][e]['start'] == 'mid' for e in eps])):
    m = np.array(m); idx = [e for e, mm in zip(eps, m) if mm]
    x = np.array([np.mean([r[e]['ate'] for r in R]) for e in idx]); y = np.array([np.mean([r[e]['ate'] for r in A]) for e in idx]); s = [sc[i] for i in range(len(eps)) if m[i]]
    print('fresh %s n=%d repmean ref %.3f/%.2f arm %.3f/%.2f d %+.3f [%+.3f,%+.3f]' % (lab, len(idx), x.mean(), np.median(x), y.mean(), np.median(y), (y - x).mean(), *boot(y - x, s)))
for k in range(reps):
    a = {e: R[k][e]['ate'] for e in eps}; b = {e: A[k][e]['ate'] for e in eps}
    nf = sum(a[e] <= 3 and b[e] > 3 for e in eps); fx = sum(a[e] > 3 and b[e] <= 3 for e in eps)
    print(f'  rep{k} confirm: >3/5/10 ref {sum(v>3 for v in a.values())}/{sum(v>5 for v in a.values())}/{sum(v>10 for v in a.values())} arm {sum(v>3 for v in b.values())}/{sum(v>5 for v in b.values())}/{sum(v>10 for v in b.values())}  newly>3 {nf} fixed {fx}  mean {np.mean(list(a.values())):.3f} -> {np.mean(list(b.values())):.3f}')
