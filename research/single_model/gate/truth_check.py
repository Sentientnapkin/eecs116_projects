import sys; sys.path.insert(0,'.')
import numpy as np, glob
from research.guard_fusion import traj as T
from research.single_model.run_variant import *
tg=tags(); e=sorted(tg)[0]
t,g,meta=load=T.load_truth(T.DEFAULT_RAW,e)
print(e,t[:5],g.shape, g[:3].round(3)); print(meta if not isinstance(meta,dict) else list(meta)[:20])
D=glob.glob(str(OUT/'gate_dbg/eval/gate_dbg-*'))[0]
f=glob.glob(f'{D}/{e}/report/logs/*/estimate.tum')[0]
print(open(f).read()[:600])
