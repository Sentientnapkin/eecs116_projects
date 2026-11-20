import sys, json; sys.path.insert(0,'.')
import numpy as np
from research.single_model.run_variant import *
def load(n): return {x['e']: x for x in json.loads((OUT / f'{n}/report.json').read_text())['rows_visible']}
ref=load(sys.argv[1])
for n in sys.argv[2:]:
    new=load(n)
    for sl in ('search','val'):
        for st in ('all','static','mid'):
            ks=[e for e in new if slice_of(new[e]['fold'])==sl and (st=='all' or new[e]['start']==st)]
            x=[ref[e]['new'] for e in ks]; y=[new[e]['new'] for e in ks]
            d,lo,hi=paired(x,y,[new[e]['scene'] for e in ks])
            ident=sum(abs(a-b)<1e-12 for a,b in zip(x,y))
            print(f'{n:14s} vs {sys.argv[1]:12s} {sl:6s} {st:6s} n={len(ks):3d} ref {np.mean(x):.3f} arm {np.mean(y):.3f} med {np.median(y):.2f} >5 {sum(v>5 for v in y)} >10 {sum(v>10 for v in y)} identical {ident} | d {d:+.3f} [{lo:+.3f},{hi:+.3f}]')
