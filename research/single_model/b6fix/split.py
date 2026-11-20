"""usage: split.py ref_table.json arm_table.json  -> dev(folds0-2)/confirm(folds3-4) paired means on fresh, tails counts"""
import sys,json,hashlib
sys.path.insert(0,'.')
import numpy as np
from research.single_model.run_variant import paired
def fold(r): return int(hashlib.sha256(f"{r['catalog']}:{r['scene']}".encode()).hexdigest()[:8],16)%5
A={r['episode']:r for r in json.load(open(sys.argv[1]))}; B={r['episode']:r for r in json.load(open(sys.argv[2]))}
for nm,sel in (('dev',lambda f:f<=2),('confirm',lambda f:f>=3),('all',lambda f:True)):
    ks=[k for k in A if sel(fold(A[k])) and B[k]['ate'] is not None]
    x=[A[k]['ate'] for k in ks]; y=[B[k]['ate'] for k in ks]
    d,lo,hi=paired(x,y,[A[k]['scene'] for k in ks])
    c=lambda v,t:sum(a>t for a in v)
    print(f'{nm:8s} n={len(ks)} ref {np.mean(x):.3f} arm {np.mean(y):.3f} d {d:+.3f} [{lo:+.3f},{hi:+.3f}] >3 {c(x,3)}->{c(y,3)} >5 {c(x,5)}->{c(y,5)} >10 {c(x,10)}->{c(y,10)}')
