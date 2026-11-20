"""first-2 s image stats (mean gray, std gray, fraction of dark/flat frames) for visible-slice flights -> early_frames.json"""
import sys, json
sys.path.insert(0,'/data/backups/rganapa/Sebastian/eecs116_projects')
import numpy as np
from pathlib import Path
from research.guard_fusion import traj as T
from viobench.tools.datasets.storage import read_episode
rows=json.load(open('research/results/single_model/diag_counters1/diag_table.json'))
out={}
for r in rows:
    e=read_episode(T.DEFAULT_RAW/f"{r['ep']}.zip")
    fr=np.asarray([e.frames[i] for i in range(0,60,2)],dtype=np.float32)
    g=fr.mean(-1) if fr.ndim==4 else fr
    m=g.mean((1,2)); s=g.std((1,2))
    out[r['ep']]=dict(mean2=float(m[:20].mean()), std2=float(s[:20].mean()), dark2=float((m[:20]<15).mean()), flat2=float((s[:20]<6).mean()),
                      mean_min=float(m[:20].min()), std_min=float(s[:20].min()), mean5=float(m.mean()), std5=float(s.mean()), flat5=float((s<6).mean()), dark5=float((m<15).mean()))
json.dump(out,open('research/results/single_model/diag_counters1/early_frames.json','w'))
print(len(out))
