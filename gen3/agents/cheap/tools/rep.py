"""rep.py POOL NAME...: paired table vs cg_goats and net_auto_727_sp10 (common flights): raw, server-weighted, per class, d vs goats [CI],
peak / p95 fuel (all frames), est. score change vs the best build: +0.404 ln(F_best/F) - 2.2 ln(sw/sw_best) (0.28 pts per fuel halving,
0.21 pts per +10 % ATE); F_best = 4.1 M (server peak of the best), F = local peak."""
import sys, json, glob, random, math, statistics as s
import numpy as np
from pathlib import Path
E = Path('/data/backups/rganapa/Sebastian/gen3/evals'); pool = sys.argv[1]
W = {'room': (12/24, 1/12), 'warehouse': (6/24, 4/6), 'forest': (6/24, 1/6)}
def load(n): return {r['id']: r for r in json.load(open(E / f'{n}__{pool}.json')) if r.get('ate') is not None}
def swm(rows):
    t = 0
    for c, (wc, hv) in W.items():
        h = [r['ate'] for r in rows if r['setting_class'] == c and r['start'] == 'hover']; m = [r['ate'] for r in rows if r['setting_class'] == c and r['start'] != 'hover']
        if not h or not m: return float('nan')
        t += wc * (hv * s.mean(h) + (1 - hv) * s.mean(m))
    return t
def p95(n, ids):
    a = []
    for i in ids:
        f = sorted(glob.glob(str(E / n / pool / f'{n}-*' / i / 'report/logs/*/fuel.npy')))
        if f: a.append(np.load(f[-1]))
    return np.percentile(np.concatenate(a), 95) if a else float('nan')
names = ['net_auto_727_sp10', 'cg_goats'] + sys.argv[2:]
R = {n: load(n) for n in names}; ids = sorted(set.intersection(*[set(r) for r in R.values()]))
best = [R['net_auto_727_sp10'][i] for i in ids]; swb = swm(best)
print(f'pool {pool}, flights in common {len(ids)}')
for n in names:
    rows = [R[n][i] for i in ids]; a = [r['ate'] for r in rows]; pk = max(r['peak'] for r in rows); sw = swm(rows)
    cl = ' '.join(f"{c[:2]} {s.mean(r['ate'] for r in rows if r['setting_class']==c):.3f}" for c in W)
    d = [R[n][i]['ate'] - R['cg_goats'][i]['ate'] for i in ids]; rng = random.Random(0); bs = sorted(s.mean(rng.choices(d, k=len(d))) for _ in range(2000))
    pts = 0.404 * math.log(4.1e6 / pk) - 2.2 * math.log(sw / swb) if n != 'net_auto_727_sp10' else 0.0
    print(f'{n:20s} raw {s.mean(a):.3f} sw {sw:.3f} med {s.median(a):.3f} >3m {sum(x>3 for x in a):3d} | {cl} | d_goats {s.mean(d):+.3f} [{bs[50]:+.3f},{bs[1949]:+.3f}] | peak {pk/1e6:.2f}M p95 {p95(n, ids)/1e6:.2f}M | est pts vs best {pts:+.2f}')
