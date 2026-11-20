import sys,glob; sys.path.insert(0,'.')
import numpy as np
from research.single_model.run_variant import *
tg=tags(); D=glob.glob(str(OUT/'gate_dbg2/eval/gate_dbg2-*'))[0]
from collections import Counter
c=Counter()
for e in sorted(tg):
    if slice_of(fold(tg[e]))!='search': continue
    a=np.loadtxt(glob.glob(f'{D}/{e}/report/logs/*/estimate.tum')[0],comments='#')
    rel=np.where(a[:,2+0-1+0]>=0)[0]  # placeholder
    r=a[:,2]; first=np.where(a[:,2]>=0)[0]
    # col1=d? columns: t x y z -> x=d(col1), y=released(col2), z=pairs(col3)
    relt=np.where(a[:,2]>0.5)[0]
    c[(tg[e]['start'], 'released' if len(relt) else 'held')]+=1
    if tg[e]['start']=='static' and len(c)<3: print(e, relt[:1], a[:12,1:4].round(2).tolist())
print(c)
