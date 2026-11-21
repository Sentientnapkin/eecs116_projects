"""cmp.py BASECFG NAME [NAME_r1 NAME_r2] : paired vs base reps (B17: lateinit gnp_r*, T4uB: tier1m T4uB, T4uBr1, T4uBr2).
dev = fresh folds 0-2, confirm = fold 3; fold 4 reported only inside 'all711' mean."""
import json, sys, hashlib, numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent
tags = json.load(open(H.parent / 'fresh/tags.json'))
fold = {e: int(hashlib.sha256((t['catalog'] + ':' + t['scene']).encode()).hexdigest()[:8], 16) % 5 for e, t in tags.items()}
BASES = {'B17': ['lateinit/tables/gnp_r0.json', 'lateinit/tables/gnp_r1.json', 'lateinit/tables/gnp_r2.json'],
         'T4uB': ['tier1m/tables/T4uB.json', 'tier1m/tables/T4uBr1.json', 'tier1m/tables/T4uBr2.json']}
def load(p):
    d = json.load(open(p)); return {r['episode']: r for r in d if r.get('ate') is not None}
bc, names = sys.argv[1], sys.argv[2:]
cand = [load(H / 'tables' / (n + '.json')) for n in names]
base = [load(H.parent / BASES[bc][k]) if bc in BASES else load(H / 'tables' / (bc + ('' if k == 0 else '_r%d' % k) + '.json')) for k in range(len(cand))]
eps = sorted(set.intersection(*[set(x) for x in base + cand]))
B = np.array([[t[e]['ate'] for e in eps] for t in base]); C = np.array([[t[e]['ate'] for e in eps] for t in cand])
sc = [tags[e]['scene'] for e in eps]; fo = np.array([fold[e] for e in eps])
rng = np.random.default_rng(1)
def boot(d, m):
    idx = np.where(m)[0]; ss = sorted(set(sc[i] for i in idx)); g = {s: [i for i in idx if sc[i] == s] for s in ss}
    bs = [d[[i for p in rng.integers(0, len(ss), len(ss)) for i in g[ss[p]]]].mean() for _ in range(1000)]
    return np.percentile(bs, [2.5, 97.5])
d = C.mean(0) - B.mean(0)
out = []
for lab, m in (('dev', fo <= 2), ('conf3', fo == 3)):
    lo, hi = boot(d, m)
    out.append('%s %.3f->%.3f %+.3f [%+.3f,%+.3f]' % (lab, B[:, m].mean(), C[:, m].mean(), d[m].mean(), lo, hi))
m = fo <= 3
tl = lambda A: '/'.join('%.1f' % x for x in [(A[:, m] > 1).sum(1).mean(), (A[:, m] > 3).sum(1).mean(), (A[:, m] > 5).sum(1).mean(), (A[:, m] > 10).sum(1).mean()])
pk = max((r.get('peak_fuel') or 0) for t in cand for r in t.values())
bw = ((d[m] < -0.3).sum(), (d[m] > 0.3).sum())
print('%-12s reps=%d | %s | f0-3 >1/3/5/10 base %s cand %s | better/worse>0.3 %d/%d | all711 %.3f->%.3f | peak %.2f M' % (
    names[0], len(cand), ' | '.join(out), tl(B), tl(C), bw[0], bw[1], B.mean(), C.mean(), pk / 1e6))
