"""Fit a small predicted-speed correction on tuning pools only."""
import argparse,json
from pathlib import Path
import numpy as np
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('name');a=p.parse_args()
d=[np.load(H/f'tables/{a.name}_{s}_pred.npz') for s in ['st2dev','st3']]
mu,lv,y=[np.concatenate([x[k] for x in d]) for k in ['mu','lv','y']];sp=np.linalg.norm(y,axis=1);pred=np.linalg.norm(mu,axis=1)
results=[]
for k in [0,.02,.04,.06,.08,.10,.12]:
 m=mu*(1+k*np.maximum(0,pred-.5))[:,None];e=np.linalg.norm(m-y,axis=1);z=(m-y)*np.exp(-lv/2)
 r=dict(speedk=k,err=float(e.mean()),fast=float(e[sp>2].mean()),criterion=float(e.mean()+.25*e[sp>2].mean()),sigma_scale=float(np.sqrt(np.mean(z*z))),bins=[float(e[q].mean()) for q in [sp<1,(sp>=1)&(sp<=2),sp>2]])
 results.append(r)
best=min(results,key=lambda r:r['criterion']);out=dict(best=best,sweep=results);(H/f'tables/{a.name}_calibration.json').write_text(json.dumps(out,indent=1));print(json.dumps(out),flush=True)
