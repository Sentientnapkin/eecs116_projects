import sys,json; sys.path.insert(0,'.')
import numpy as np
from research.guard_fusion import traj as T
from research.single_model.run_variant import tags,fold
tg=tags()
for e in sys.argv[1:]:
    assert fold(tg[e])!=4
    t,g,m=T.load_truth(T.DEFAULT_RAW,e); v=np.linalg.norm(g[:,7:10],axis=1); t=t-t[0]
    print(e,'true speed mean t<=0.45: %.2f  at 0.6-0.7: %.2f  at 1s %.2f'%(v[t<=0.45].mean(),v[(t>=.6)&(t<=.7)].mean(),v[(t>=.95)&(t<=1.05)].mean()))
