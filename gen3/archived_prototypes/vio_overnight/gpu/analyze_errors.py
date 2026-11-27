#!/usr/bin/env python3
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path('/data/backups/rganapa/Sebastian/gen3/research/overnight_20261127/gpu')
LAGS={'.25s':5,'.5s':10,'1s':20,'2s':40,'5s':100}
def corr(a,b):
 if len(a)<2 or np.std(a)<1e-9 or np.std(b)<1e-9:return None
 return float(np.corrcoef(a,b)[0,1])
def run(path):
 d=np.load(path,allow_pickle=True); e=(d['mu'].astype(np.float32)-d['y'].astype(np.float32)); fid=d['fid'].astype(int); pos=d['pos'].astype(int); names=d['flight_names'].astype(str)
 mag=np.linalg.norm(e,axis=-1); rows=[]
 for f in np.unique(fid):
  ix=np.where(fid==f)[0]; order=np.argsort(pos[ix]); ix=ix[order]; lookup={int(pos[j]):j for j in ix}; row={'flight':str(names[f]),'anchors':len(ix),'lags':{}}
  for name,lag in LAGS.items():
   a=[];b=[];dot=[]
   for j in ix:
    k=lookup.get(int(pos[j])+lag)
    if k is not None:
     a.append(mag[j]);b.append(mag[k]);dot.append(float(np.dot(e[j],e[k])))
   row['lags'][name]={'pairs':len(a),'magnitude_corr':corr(np.asarray(a),np.asarray(b)) if a else None,'residual_dot_mean':float(np.mean(dot)) if dot else None}
  rows.append(row)
 pooled={}
 for name in LAGS:
  vals=[r['lags'][name]['magnitude_corr'] for r in rows if r['lags'][name]['magnitude_corr'] is not None]
  pooled[name]={'flight_count':len(vals),'mean_flight_magnitude_corr':float(np.mean(vals)) if vals else None}
 out={'prediction_file':path.name,'units':'frames at 20Hz; lag labels in seconds','pooled':pooled,'per_flight':rows}
 target=path.parent/'temporal_error_correlation.json';target.write_text(json.dumps(out,indent=2)+'\n');return target
if __name__=='__main__':
 p=Path(sys.argv[1]);print(run(p))
