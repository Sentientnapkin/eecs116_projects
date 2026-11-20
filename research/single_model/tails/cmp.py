"""usage: cmp.py arm [arm...]   paired scene-bootstrap vs f0 (final_f0), search slice (+val summary). Fold 4 never read."""
import sys, json; sys.path.insert(0, '.')
import numpy as np
from research.single_model.run_variant import OUT, slice_of, paired
def load(n): return {x['e']: x for x in json.loads((OUT / f'{n}/report.json').read_text())['rows_visible']}
ref = load('final_f0')
for n in sys.argv[1:]:
    new = load(n)
    for sl in ('search', 'val'):
        for st in ('all', 'static', 'mid'):
            ks = [e for e in new if slice_of(new[e]['fold']) == sl and (st == 'all' or new[e]['start'] == st)]
            x = [ref[e]['new'] for e in ks]; y = [new[e]['new'] for e in ks]
            d, lo, hi = paired(x, y, [new[e]['scene'] for e in ks])
            print(f'{n:12s} {sl:6s} {st:6s} n={len(ks):3d} f0 {np.mean(x):.3f} arm {np.mean(y):.3f} med {np.median(y):.2f} >3 {sum(v>3 for v in y)} >5 {sum(v>5 for v in y)} >10 {sum(v>10 for v in y)} | d {d:+.3f} [{lo:+.3f},{hi:+.3f}]')
