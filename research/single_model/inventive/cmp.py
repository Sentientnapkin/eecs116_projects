"""usage: cmp.py arm [arm...]  single-run paired bootstrap vs inv_gbase_r0 (search+val). cmp.py -r arm : 3-replicate mean vs inv_gbase_r0..2"""
import sys, json; sys.path.insert(0, '.')
import numpy as np
from research.single_model.run_variant import OUT, slice_of, paired
def load(n): return {x['e']: x for x in json.loads((OUT / f'{n}/report.json').read_text())['rows_visible']}
args = sys.argv[1:]; rep = args[0] == '-r'
if rep: args = args[1:]
refs = [load(f'inv_gbase_r{i}') for i in range(3)] if rep else [load('inv_gbase_r0')]
for n in args:
    news = [load(f'{n}_r{i}') for i in range(3)] if rep else [load(n)]
    for sl in ('search', 'val'):
        for st in ('all', 'static', 'mid'):
            ks = [e for e in news[0] if slice_of(news[0][e]['fold']) == sl and (st == 'all' or news[0][e]['start'] == st)]
            x = [np.mean([r[e]['new'] for r in refs]) for e in ks]; y = [np.mean([r[e]['new'] for r in news]) for e in ks]
            d, lo, hi = paired(x, y, [news[0][e]['scene'] for e in ks])
            gt = lambda rr, t: [sum(r[e]['new'] > t for e in ks) for r in rr]
            print(f'{n:16s} {sl:6s} {st:6s} n={len(ks):3d} ref {np.mean(x):.3f} arm {np.mean(y):.3f} | d {d:+.3f} [{lo:+.3f},{hi:+.3f}] | >5 ref {gt(refs,5)} arm {gt(news,5)} >10 ref {gt(refs,10)} arm {gt(news,10)}')
