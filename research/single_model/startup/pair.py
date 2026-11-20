"""usage: pair.py ref arm... : paired scene-bootstrap of arms vs ref (search slice, plus val if --val)."""
import sys, json; sys.path.insert(0, '.')
import numpy as np
from research.single_model.run_variant import *
def load(n): return {x['e']: x for x in json.loads((OUT / f'startup_{n}/report.json').read_text())['rows_visible']}
val = '--val' in sys.argv; a = [x for x in sys.argv[1:] if not x.startswith('--')]
ref = load(a[0])
for n in a[1:]:
    new = load(n)
    for sl in (('search', 'val') if val else ('search',)):
        for st in ('all', 'mid'):
            ks = [e for e in new if slice_of(new[e]['fold']) == sl and (st == 'all' or new[e]['start'] == st)]
            x = [ref[e]['new'] for e in ks]; y = [new[e]['new'] for e in ks]
            d, lo, hi = paired(x, y, [new[e]['scene'] for e in ks])
            print(f'{n:14s} vs {a[0]:8s} {sl:6s} {st:4s} ref {np.mean(x):.3f} arm {np.mean(y):.3f} med {np.median(y):.2f} >5 {sum(v>5 for v in y)} >10 {sum(v>10 for v in y)} | d {d:+.3f} [{lo:+.3f},{hi:+.3f}]')
