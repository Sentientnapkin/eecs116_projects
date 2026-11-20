"""Compare arms against startup_base (search slice always; val with --val). Never reads sealed output."""
import sys, json
sys.path.insert(0, '.')
import numpy as np
from pathlib import Path
from research.single_model.run_variant import *
tg = tags(); O = OUT
def load(n):
    r = json.loads((O / f'startup_{n}/report.json').read_text())
    return {x['e']: x for x in r['rows_visible']}
base = load('base')
val = '--val' in sys.argv
names = [a for a in sys.argv[1:] if not a.startswith('--')]
print(f'{"arm":14s} slice  grp    mean  med  >5 >10 | d vs base [95% CI]')
for n in names:
    new = load(n)
    for sl in (('search', 'val') if val else ('search',)):
        for st in ('all', 'static', 'mid'):
            ks = [e for e in new if slice_of(new[e]['fold']) == sl and (st == 'all' or new[e]['start'] == st)]
            a = [base[e]['new'] for e in ks]; b = [new[e]['new'] for e in ks]
            d, lo, hi = paired(a, b, [new[e]['scene'] for e in ks])
            print(f'{n:14s} {sl:6s} {st:6s} {np.mean(b):5.3f} {np.median(b):4.2f} {sum(x>5 for x in b):2d} {sum(x>10 for x in b):2d} | {d:+.3f} [{lo:+.3f},{hi:+.3f}]  (base {np.mean(a):.3f})')
