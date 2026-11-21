"""cmp.py CAND_PREFIX [reps=3]: compare fuel_b13/tables/<CAND_PREFIX>{,r1,r2}.json (rep0 name = PREFIX, rep k name = PREFIXr<k>) against frozen B13 xC reps (bulk/tables/bk_xC{,r1,r2}.json), paired by episode."""
import json, sys, numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent
def load(p):
    d = json.load(open(p)); return {r['episode']: r for r in d if r['ate'] is not None}
pre = sys.argv[1]; R = int(sys.argv[2]) if len(sys.argv) > 2 else 3
base = [load(H.parent / 'bulk/tables' / n) for n in ['bk_xC.json', 'bk_xCr1.json', 'bk_xCr2.json'][:R]]
cand = []
for k in range(R):
    p = H / 'tables' / (pre + ('' if k == 0 else 'r%d' % k) + '.json')
    if p.exists(): cand.append(load(p))
R = len(cand); base = base[:R]
eps = sorted(set.intersection(*[set(x) for x in base + cand]))
sc = {r['episode']: r['scene'] for r in json.load(open(H.parent / 'bulk/tables/bk_xC.json'))}
rng = np.random.default_rng(1)
def stats(tabs):
    A = np.array([[t[e]['ate'] for e in eps] for t in tabs]); return A
B, C = stats(base), stats(cand)
scenes = sorted(set(sc[e] for e in eps)); idx = {s: [i for i, e in enumerate(eps) if sc[e] == s] for s in scenes}
d = (C.mean(0) - B.mean(0)); boots = []
for _ in range(2000):
    pick = rng.integers(0, len(scenes), len(scenes)); sel = [i for p in pick for i in idx[scenes[p]]]; boots.append(d[sel].mean())
lo, hi = np.percentile(boots, [2.5, 97.5])
pk = max((r['peak_fuel'] or 0) for t in cand for r in t.values())
print('%s reps=%d n=%d | base mean per rep %s (avg %.3f) | cand %s (avg %.3f) | paired(rep-avg) d=%+.3f [%+.3f,%+.3f] | >3/5/10 base %s cand %s | peak fuel %.2f M' % (
    pre, R, len(eps), np.round(B.mean(1), 3), B.mean(), np.round(C.mean(1), 3), C.mean(), d.mean(), lo, hi,
    '/'.join('%.1f' % x for x in [(B > 3).sum(1).mean(), (B > 5).sum(1).mean(), (B > 10).sum(1).mean()]),
    '/'.join('%.1f' % x for x in [(C > 3).sum(1).mean(), (C > 5).sum(1).mean(), (C > 10).sum(1).mean()]), pk / 1e6))
print('   worst flight cand rep-avg %.2f (base %.2f); flights newly >3 m (rep-avg): %d, fixed: %d; mean of per-rep max %.2f (base %.2f)' % (C.mean(0).max(), B.mean(0).max(), ((C.mean(0) > 3) & (B.mean(0) <= 3)).sum(), ((C.mean(0) <= 3) & (B.mean(0) > 3)).sum(), C.max(1).mean(), B.max(1).mean()))
