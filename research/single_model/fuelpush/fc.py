"""fc.py NAME [NAMEr1 NAMEr2] : fresh-711 paired vs T4uB reps (tier1m/tables/T4uB,T4uBr1,T4uBr2) and B17 (lateinit gnp_r*);
dev = folds 0-2, confirm = fold 3 (fold 4 only in the overall mean); tails; peak; area vs B16 point and vs T4uB."""
import json, sys, hashlib, numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent
tags = json.load(open(H.parent / 'fresh/tags.json'))
fold = {e: int(hashlib.sha256((t['catalog'] + ':' + t['scene']).encode()).hexdigest()[:8], 16) % 5 for e, t in tags.items()}
def load(p):
    d = json.load(open(p)); return {r['episode']: r for r in d if r.get('ate') is not None and r['episode'] in tags}
names = sys.argv[1:]
cand = [load(H / 'tables' / (n + '.json')) for n in names]
refs = {'T4uB': [H.parent / 'tier1m/tables' / f for f in ('T4uB.json', 'T4uBr1.json', 'T4uBr2.json')],
        'B17': [H.parent / 'lateinit/tables' / ('gnp_r%d.json' % k) for k in range(3)]}
pk = max((r.get('peak_fuel') or 0) for t in cand for r in t.values()) / 1e6
nfill = sum(1 for t in cand for r in t.values() if r.get('filled'))
eps = sorted(set.intersection(*[set(x) for x in cand]))
C = np.array([[t[e]['ate'] for e in eps] for t in cand]); cm = C.mean()
dev = np.array([fold[e] <= 2 for e in eps]); conf = np.array([fold[e] == 3 for e in eps])
tl = lambda A: '/'.join('%.1f' % x for x in [(A > 3).sum(1).mean(), (A > 5).sum(1).mean(), (A > 10).sum(1).mean()])
area16 = 0.28 * np.log2(17 / pk) - 2.24 * np.log(cm / 0.356)
area4 = 0.28 * np.log2(4.10 / pk) - 2.24 * np.log(cm / 0.381)
print('%s reps=%d n=%d mean %.3f (per rep %s) dev %.3f conf(f3) %.3f | >3/5/10 %s | peak %.2f M filled %d | area vs B16 %+.2f vs T4uB %+.2f' % (
    names[0], len(cand), len(eps), cm, np.round(C.mean(1), 3), C[:, dev].mean(), C[:, conf].mean(), tl(C), pk, nfill, area16, area4))
sc = {e: tags[e]['scene'] for e in eps}; rng = np.random.default_rng(1)
for rn, paths in refs.items():
    B = [load(p) for p in paths[:len(cand)]]
    Bm = np.array([[b[e]['ate'] for e in eps] for b in B]); d = C.mean(0) - Bm.mean(0)
    ss = sorted(set(sc.values())); g = {s: [i for i in range(len(eps)) if sc[eps[i]] == s] for s in ss}
    bs = [d[[i for p in rng.integers(0, len(ss), len(ss)) for i in g[ss[p]]]].mean() for _ in range(1000)]
    print('   vs %s (%d reps) %.3f: d %+.3f [%+.3f,%+.3f] dev %+.3f conf %+.3f | ref tails %s' % (rn, len(B), Bm.mean(), d.mean(), *np.percentile(bs, [2.5, 97.5]), d[dev].mean(), d[conf].mean(), tl(Bm)))
