"""usage: cmprep.py refname armname  : compares mean over the 3 chaos replicates (name_r0..2), per flight, paired scene bootstrap."""
import sys, json; sys.path.insert(0, '.')
import numpy as np
from research.single_model.run_variant import OUT, slice_of, paired
def load(n):
    runs=[{x['e']: x for x in json.loads((OUT / f'{n}_r{i}/report.json').read_text())['rows_visible']} for i in range(3)]
    return runs
ref = load(sys.argv[1])
for n in sys.argv[2:]:
    new = load(n)
    print(n, 'per-replicate search mean:', [round(np.mean([r[e]['new'] for e in r if slice_of(r[e]['fold'])=='search']),3) for r in new],
          ' ref', [round(np.mean([r[e]['new'] for e in r if slice_of(r[e]['fold'])=='search']),3) for r in ref])
    for sl in ('search', 'val'):
        for st in ('all', 'static', 'mid'):
            ks = [e for e in new[0] if slice_of(new[0][e]['fold']) == sl and (st == 'all' or new[0][e]['start'] == st)]
            x = [np.mean([r[e]['new'] for r in ref]) for e in ks]; y = [np.mean([r[e]['new'] for r in new]) for e in ks]
            d, lo, hi = paired(x, y, [new[0][e]['scene'] for e in ks])
            ct=lambda rr:[sum(r[e]['new']>3 for e in ks) for r in rr]
            print(f'  {sl:6s} {st:6s} n={len(ks):3d} ref {np.mean(x):.3f} arm {np.mean(y):.3f} | d {d:+.3f} [{lo:+.3f},{hi:+.3f}] | >3 per rep ref {ct(ref)} arm {ct(new)}')
