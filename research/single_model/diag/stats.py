import json, sys
import numpy as np
from pathlib import Path
ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects')
name=sys.argv[1] if len(sys.argv)>1 else 'diag_counters1'
rows=json.loads((ROOT/'research/results/single_model'/name/'diag_table.json').read_text())
BENCH=Path('/data/backups/rganapa/Sebastian/gen/raw-fast/bench')
for r in rows:
    a=json.loads((BENCH/f"{r['ep']}.json").read_text())['audit']
    for k in ('dark_fraction','flat_fraction','speed_p10_p50_p90','hover_fraction','turning_fraction','travel_m'):
        r[k]=a[k]
    r['bad']= r['ate']>3.5 if False else None
def sel(sl,st='mid'): return [r for r in rows if r['slice']==sl and r['start']==st]
def col(rs,k): return np.array([r.get(k,np.nan) for r in rs],float)
def summ(rs,k):
    x=col(rs,k); return f"{np.nanmean(x):.3f}/{np.nanmedian(x):.3f}"
if __name__=='__main__':
    pass
