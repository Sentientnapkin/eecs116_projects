"""python -m research.single_model.robust.bands B7 soft ... : per-flight failure probability p = fraction of replicates >3 m.
persistently bad p=1, sometimes bad 0<p<1 (chaos band), persistently good p=0. Also expected failures sum(p) and mid-forward (angle<90) subset."""
import json, sys, numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent
tf = {r['episode']: r for r in json.loads((H.parent / 'fresh/truth_feats.json').read_text())}
print(f'{"arm":9s} {"subset":9s} n    persist-bad  sometimes  persist-good  E[fail]  mean p(sometimes)  P(12 clean | p iid)')
for n in sys.argv[1:]:
    rows = json.loads((H / 'out' / n / 'replicates_fresh.json').read_text())['rows']
    for nm, f in (('all', lambda r: True), ('mid-fwd', lambda r: r['start'] == 'mid' and tf[r['episode']]['angle'] < 90), ('static', lambda r: r['start'] == 'static')):
        A = np.array([r['reps'] for r in rows if f(r)]); p = (A > 3).mean(1)
        pb, sb, gd = (p == 1).sum(), ((p > 0) & (p < 1)).sum(), (p == 0).sum()
        pc = float(np.prod(1 - p[np.random.default_rng(0).permutation(len(p))[:12]])) if False else float(np.mean([np.prod(1 - p[np.random.default_rng(i).choice(len(p), 12)]) for i in range(2000)]))
        print(f'{n:9s} {nm:9s} {len(p):3d}  {pb:4d} ({100*pb/len(p):.1f}%) {sb:4d} ({100*sb/len(p):.1f}%) {gd:4d} ({100*gd/len(p):.1f}%)  {p.sum():6.1f}  {p[(p>0)&(p<1)].mean() if sb else 0:.2f}   {pc:.3f}')
