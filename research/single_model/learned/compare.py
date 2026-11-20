"""Paired bootstrap (scenes) of learned arm vs baseline and vs the heading-prior arm, per slice and start type.
python -B compare.py learned_sd64_B [more...]   (reads report.json rows_visible; sealed rows are not in them)"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from research.single_model.run_variant import paired
R = Path(__file__).resolve().parents[2] / 'results/single_model'
def rows(n):
    return {r['e']: r for r in json.load(open(R / n / 'report.json'))['rows_visible']}
ref = rows('startup_c2c_head')
for n in sys.argv[1:]:
    a = rows(n)
    for sl in ('search', 'val'):
        for st in ('all', 'static', 'mid'):
            ks = [e for e in a if e in ref and (('search' if a[e]['fold'] in (0, 1, 2) else 'val') == sl) and (st == 'all' or a[e]['start'] == st)]
            new = [a[e]['new'] for e in ks]; base = [a[e]['base'] for e in ks]; h = [ref[e]['new'] for e in ks]; sc = [a[e]['scene'] for e in ks]
            d1 = paired(base, new, sc); d2 = paired(h, new, sc)
            print(f'{n:22s} {sl:6s} {st:6s} n={len(ks):3d} mean {np.mean(new):.3f} | heading {np.mean(h):.3f} | vs base {d1[0]:+.3f} [{d1[1]:+.3f},{d1[2]:+.3f}] | vs heading {d2[0]:+.3f} [{d2[1]:+.3f},{d2[2]:+.3f}]')
