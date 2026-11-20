"""usage: summ.py arm... : table of single runs (search all/static/mid, >5, >10; val all) with paired d vs inv_gbase_r0"""
import sys, json; sys.path.insert(0, '.')
import numpy as np
from research.single_model.run_variant import OUT, slice_of, paired
L = lambda n: {x['e']: x for x in json.loads((OUT / f'{n}/report.json').read_text())['rows_visible']}
ref = L('inv_gbase_r0')
print(f'{"arm":14s} search  static  mid   >5 >10 | d vs gbase_r0 [CI] | val')
for n in sys.argv[1:]:
    try: a = L(n)
    except Exception: print(n, 'missing'); continue
    S = [e for e in a if slice_of(a[e]['fold']) == 'search']; V = [e for e in a if slice_of(a[e]['fold']) == 'val']
    m = lambda ks, st=None: np.mean([a[e]['new'] for e in ks if st is None or a[e]['start'] == st])
    d, lo, hi = paired([ref[e]['new'] for e in S], [a[e]['new'] for e in S], [a[e]['scene'] for e in S])
    print(f'{n:14s} {m(S):.3f}  {m(S,"static"):.3f}  {m(S,"mid"):.3f}  {sum(a[e]["new"]>5 for e in S):2d} {sum(a[e]["new"]>10 for e in S):2d} | {d:+.3f} [{lo:+.3f},{hi:+.3f}] | {m(V):.3f}')
