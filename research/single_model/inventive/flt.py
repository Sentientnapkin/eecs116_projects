"""usage: flt.py ref arm [thr] : per-flight diff (search+val) sorted"""
import sys, json; sys.path.insert(0, '.')
from research.single_model.run_variant import OUT, slice_of
L = lambda n: {x['e']: x for x in json.loads((OUT / f'{n}/report.json').read_text())['rows_visible']}
a, b = L(sys.argv[1]), L(sys.argv[2])
d = sorted(((b[e]['new'] - a[e]['new'], e, a[e]['new'], b[e]['new'], a[e]['start'], slice_of(a[e]['fold'])) for e in a), key=lambda x: x[0])
n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
for x in d[:n] + [None] + d[-n:]:
    print('...' if x is None else f'{x[1]:45s} {x[4]:6s} {x[5]:6s} {x[2]:.3f} -> {x[3]:.3f} ({x[0]:+.3f})')
print('changed', sum(abs(x[0]) > 1e-9 for x in d), 'of', len(d))
