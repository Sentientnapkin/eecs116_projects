"""Paired comparison of lateinit arms vs B16 (tailcap/tables/b16r_r*.json) on dev / confirm.
  python cmp.py arm[,arm2] [--reps K]   (replicate k of the arm is paired with replicate k of B16)"""
import json, sys
import numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
FS = json.load(open(HERE / '../tailcap/fresh_sets.json'))
FE = json.load(open(HERE / '../learned_c/feats.json'))
def grp(r):
    e = r['episode']
    if r['set'] == 'fresh': return 'dev' if FS[e]['fold'] < 3 else 'conf'
    return 'dev' if FE[e]['fold'] < 3 else 'conf'
def load(p): return {(r['set'], r['episode']): r for r in json.load(open(p))}
reps = int(sys.argv[sys.argv.index('--reps') + 1]) if '--reps' in sys.argv else 1
rng = np.random.default_rng(0)
for arm in sys.argv[1].split(','):
    for k in range(reps):
        pa = HERE / 'tables' / f'{arm}_r{k}.json'
        if not pa.exists(): continue
        A = load(pa); B = load(HERE / f'../tailcap/tables/b16r_r{k}.json')
        keys = [q for q in A if q in B]
        same = sum(A[q]['ate'] == B[q]['ate'] for q in keys)
        line = f'{arm:10s} r{k} n={len(keys)} identical={same}'
        for g in ('dev', 'conf'):
            ks = [q for q in keys if grp(A[q]) == g]
            if not ks: continue
            a = np.array([A[q]['ate'] for q in ks]); b = np.array([B[q]['ate'] for q in ks]); d = a - b
            bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
            fa = max(A[q]['peak_fuel'] or 0 for q in ks) / 1e6
            line += f' | {g} {len(ks)}: {b.mean():.3f}->{a.mean():.3f} d {d.mean():+.3f} [{np.percentile(bs,2.5):+.3f},{np.percentile(bs,97.5):+.3f}] >1 {(b>1).sum()}->{(a>1).sum()} >3 {(b>3).sum()}->{(a>3).sum()} >5 {(b>5).sum()}->{(a>5).sum()} >10 {(a>10).sum()} better/worse>0.3 {(d<-0.3).sum()}/{(d>0.3).sum()} peak {fa:.1f}M'
        print(line)
