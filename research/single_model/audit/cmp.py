"""cmp.py NAME [NAME_r1 NAME_r2] : fresh-711 paired vs T4uB reps (tier1m/tables/T4uB, T4uBr1, T4uBr2) or BASE=b0,b1,b2 (audit table names);
dev (folds 0-2) / confirm (3-4), tails, peak, scene-bootstrap CI."""
import json, sys, os, hashlib, numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent
tags = json.load(open(H.parent / 'fresh/tags.json'))
fold = {e: int(hashlib.sha256((t['catalog'] + ':' + t['scene']).encode()).hexdigest()[:8], 16) % 5 for e, t in tags.items()}
def load(p):
    d = json.load(open(p)); return {r['episode']: r for r in d if r.get('ate') is not None and r['episode'] in tags}
def tab(n):
    p = H / 'tables' / (n + '.json')
    return p if p.exists() else H.parent / 'tier1m/tables' / (n + '.json')
names = sys.argv[1:]
cand = [load(tab(n)) for n in names]
bn = os.environ.get('BASE', 'T4uB,T4uBr1,T4uBr2').split(',')
base = [load(tab(bn[k])) for k in range(len(cand))]
eps = sorted(set.intersection(*[set(x) for x in base + cand]))
nfail = sum(1 for t in [json.load(open(tab(n))) for n in names] for r in t if r.get('ate') is None or (r.get('filled') or 0) > 0)
B = np.array([[t[e]['ate'] for e in eps] for t in base]); C = np.array([[t[e]['ate'] for e in eps] for t in cand])
sc = {e: tags[e]['scene'] for e in eps}
rng = np.random.default_rng(1)
def boot(d, m):
    idx = [i for i in range(len(eps)) if m[i]]; ss = sorted(set(sc[eps[i]] for i in idx)); g = {s: [i for i in idx if sc[eps[i]] == s] for s in ss}
    bs = []
    for _ in range(1000):
        pick = rng.integers(0, len(ss), len(ss)); sel = [i for p in pick for i in g[ss[p]]]; bs.append(d[sel].mean())
    return np.percentile(bs, [2.5, 97.5])
d = C.mean(0) - B.mean(0)
dev = np.array([fold[e] <= 2 for e in eps]); conf = ~dev
lo, hi = boot(d, np.ones(len(eps), bool))
pk = max((r.get('peak_fuel') or 0) for t in cand for r in t.values())
tl = lambda A, m: '/'.join('%.1f' % x for x in [(A[:, m] > 3).sum(1).mean(), (A[:, m] > 5).sum(1).mean(), (A[:, m] > 10).sum(1).mean()])
al = np.ones(len(eps), bool)
nch = int((np.abs(d) > 1e-9).sum())
print('%s reps=%d n=%d | base %.3f cand %.3f (per rep %s) d=%+.4f [%+.3f,%+.3f] | dev %+.3f conf %+.3f | >3/5/10 base %s cand %s | peak %.2f M | changed %d | fail/filled %d' % (
    names[0], len(cand), len(eps), B.mean(), C.mean(), np.round(C.mean(1), 3), d.mean(), lo, hi, d[dev].mean(), d[conf].mean(), tl(B, al), tl(C, al), pk / 1e6, nch, nfail))
