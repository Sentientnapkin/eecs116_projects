#!/usr/bin/env python3
"""Finite read-only MSCKF trajectory audit; no evaluator/build/remote data access."""
import json, math
from pathlib import Path
import numpy as np
G=Path('/data/backups/rganapa/Sebastian/gen3')
ROOT=G.parent/'eecs116_projects'
OUT=Path('/tmp/vio_loop3/classical')
CACHE=G/'research/i2/cache_t'  # GT positions only; old filter traces are never used.
EVAL=G/'evals/an_snace6e1/v3val/an_snace6e1-1a169f28'
RESULT=G/'evals/an_snace6e1__v3val.json'
BASE=G/'scratch_up/gslv_s3_snace6e1.wasm'
EXPECTED='1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8'

def main():
 import hashlib
 sha=hashlib.sha256(BASE.read_bytes()).hexdigest()
 if sha!=EXPECTED: raise RuntimeError(f'baseline hash mismatch: {sha}')
 screen=json.loads((Path('/tmp/vio_loop2/shared/screen24_baseline.json')).read_text())
 confirm=json.loads((Path('/tmp/vio_loop2/shared/confirm48_baseline.json')).read_text())
 if len(screen['rows'])!=24 or len(confirm['rows'])!=48 or screen['baseline_sha256']!=EXPECTED or confirm['baseline_sha256']!=EXPECTED:
  raise RuntimeError('shared baseline controls missing or hash mismatch')
 published={r['id']:r for r in json.loads(RESULT.read_text())}
 rows=[]; missing=[]; ate_diffs=[]
 for eid,r in published.items():
  npz=CACHE/f'{eid}.npz'; logs=sorted((EVAL/eid/'report/logs').glob('*/estimate.tum'))
  if not npz.exists() or not logs: missing.append(eid); continue
  z=np.load(npz); t=z['t']; gt=z['pg']
  a=np.loadtxt(logs[0],comments='#'); et=a[:,0]; ep=a[:,1:4]
  # Report timestamp convention is offset by exactly one image midpoint (37.5 ms).
  est=np.stack([np.interp(t+.0375,et,ep[:,j]) for j in range(3)],axis=1)
  err=est-gt; mag=np.linalg.norm(err,axis=1); ate=float(np.sqrt(np.mean(mag**2)))
  ate_diffs.append(abs(ate-float(r['ate'])))
  at={str(s):float(mag[min(int(round(s*20)),len(mag)-1)]) for s in [.25,.5,1,2,5,10,20,30,40,50,59.95]}
  rows.append({'id':eid,'ate':ate,'source_ate':r['ate'],'path_gt_m':float(np.linalg.norm(np.diff(gt,axis=0),axis=1).sum()),'horizons_m':at,
    'peak5s_m': [float(np.sqrt(np.mean(mag[i:i+100]**2))) for i in range(0,len(mag),100)]})
 if len(rows)!=358: raise RuntimeError(f'coverage {len(rows)}/358; absent={len(missing)}')
 rows.sort(key=lambda r:r['ate']); best=rows[:36]; worst=rows[-36:]
 med=lambda group,fn:float(np.median([fn(x) for x in group]))
 tkeys=['0.25','0.5','1','2','5','10','20','30','40','50','59.95']
 summary={'baseline_sha256':sha,'screen_control_n':24,'confirm_control_n':48,'n':len(rows),'max_abs_ate_reproduction_error':max(ate_diffs),
  'worst6':[{'id':r['id'],'ate':r['ate'],'at_025':r['horizons_m']['0.25'],'at_2':r['horizons_m']['2'],'at_10':r['horizons_m']['10'],'at_30':r['horizons_m']['30'],'at_50':r['horizons_m']['50'],'at_end':r['horizons_m']['59.95'],'path':r['path_gt_m']} for r in rows[-6:]],
  'best6':[{'id':r['id'],'ate':r['ate'],'at_025':r['horizons_m']['0.25'],'at_2':r['horizons_m']['2'],'at_10':r['horizons_m']['10'],'at_50':r['horizons_m']['50'],'at_end':r['horizons_m']['59.95'],'path':r['path_gt_m']} for r in rows[:6]],
  'worst_decile_median_by_time':{k:med(worst,lambda r:r['horizons_m'][k]) for k in tkeys},
  'best_decile_median_by_time':{k:med(best,lambda r:r['horizons_m'][k]) for k in tkeys},
  'worst_decile_median_5s_rms': [med(worst,lambda r:r['peak5s_m'][i]) for i in range(12)],
  'interpretation':'Current errors begin elevated on some worst flights but continue to grow or recur later. Worst 6 include both early-large and late-onset failures; no shared start-only pattern or evidence identifying stale anchors/feature discontinuity. No one-change intervention is causally justified by pose/GT alone; queue stays empty pending model-level instrumentation. No yaw-axis attribution.'}
 (OUT/'diagnostic.json').write_text(json.dumps(summary,indent=2)+'\n')
 (OUT/'queue.json').write_text(json.dumps({'status':'model-review-needed','candidates':[],'reason':'trajectory timing separates early from late divergence but does not identify a causal control surface; do not blind-sweep initialization, covariance, anchors, or track management.'},indent=2)+'\n')
 (OUT/'rows.json').write_text(json.dumps(rows)+'\n')
 with (OUT/'status.log').open('a') as f:f.write(f"DONE diagnostic n={len(rows)} max_ate_repro_error={max(ate_diffs):.3g}; model-review-needed; no candidate evaluation queued\\n")
if __name__=='__main__':main()
