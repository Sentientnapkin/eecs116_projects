#!/usr/bin/env python3
"""Associate same-run framewise pose-error increments with estimator events; descriptive only."""
import json,re
from pathlib import Path
import numpy as np
ROOT=Path('/data/backups/rganapa/Sebastian/gen3')
RUN=Path('/tmp/vio_loop3/telemetry/eval2/telemetry-d698a4e1')
OUT=Path('/tmp/vio_loop3/telemetry')
BAD=['s3v3va-wa-9300423','s3v3va-ro-9300224','s3v3va-wa-9300313','s3v3va-ro-9300016','s3v3va-ro-9300242']
GOOD=['s3v3va-ro-9300284','s3v3va-ro-9300157','s3v3va-ro-9300201','s3v3va-ro-9300231']

def one(eid):
 d=next((RUN/eid/'report/logs').glob('*/'))
 est=np.loadtxt(d/'estimate.tum',comments='#'); z=np.load(ROOT/'research/i2/cache_t'/f'{eid}.npz'); t=z['t']; gt=z['pg']
 ep=np.stack([np.interp(t+.0375,est[:,0],est[:,j]) for j in range(1,4)],1)-gt
 inc=np.r_[np.nan,np.linalg.norm(np.diff(ep,axis=0),axis=1)]
 lines=(d/'stderr.txt').read_text().splitlines(); ts=[]; ss=[]
 for l in lines:
  if l.startswith('T '):
   q=l.split(); ts.append([int(q[1]),int(q[2]),int(q[3]),int(q[4]),int(q[5]),int(q[6]),np.array([float(v) for v in q[q.index('cov')+1:]])])
  elif l.startswith('S '): ss.append(list(map(int,l.split()[1:])))
 T={r[0]:r for r in ts}; S={r[0]:r[1:] for r in ss}; n=min(len(inc),max(T))
 # event predicates based only on this flight; each predicate is per-frame nonzero. Track-drop needs adjacent live counts.
 ev={k:[] for k in ['anchor','gate_or_tri_rej','map_match','map_accept','klt_fail','track_drop']}
 for f in range(2,n+1):
  tr=T[f]; sr=S[f]; prev=T[f-1]
  # S columns after frame: live,att,tri,gate,... kfail at index 11; map_match index 20; accept 21
  if tr[1]>prev[1]: ev['anchor'].append(f)
  if sr[3]>0 or sr[1]>sr[2]: ev['gate_or_tri_rej'].append(f)
  if sr[20]>0: ev['map_match'].append(f)
  if sr[21]>0: ev['map_accept'].append(f)
  if sr[11]>0: ev['klt_fail'].append(f)
  if S[f][0]<S[f-1][0]: ev['track_drop'].append(f)
 # Correct anchor delta is nanch, not comparison above; recover change exactly.
 ev['anchor']=[f for f in range(2,n+1) if T[f][1]>T[f-1][1]]
 # per flight robust normalizer: Q90 increment; covariance diagonals are instrument-frame proxy (no camera transform/NEES claim).
 q90=float(np.nanquantile(inc[:n],.90)); out={}
 for name,frames in ev.items():
  out[name]={}
  for lag in range(3):
   ix=np.array([f-1+lag for f in frames if 0<=f-1+lag<n],int)
   vals=inc[ix]; vals=vals[np.isfinite(vals)]
   mask=np.zeros(n,bool); mask[ix]=True; ref=inc[:n][(~mask) & np.isfinite(inc[:n])]; out[name][str(lag)]={'n':int(len(vals)),'median':float(np.median(vals)) if len(vals) else None,'q90_normalized_median':float(np.median(vals)/q90) if len(vals) and q90 else None,'above_flight_q90':int(np.sum(vals>q90)),'non_event_q90_normalized_median':float(np.median(ref)/q90) if len(ref) and q90 else None}
 # in-band covariance proxy median sum of 3 orientation+velocity+accel-bias diagonal slots; frame native coordinates only.
 return {'id':eid,'group':'bad' if eid in BAD else 'good','error_increment_q90':q90,'events':out,
         'covdiag_proxy_median':{k:float(np.median([r[6][a:b].sum() for r in ts])) for k,a,b in [('TH',0,3),('V',3,6),('BG',9,12)]}}

rows=[one(x) for x in BAD+GOOD]
summary={'n':len(rows),'bad_ids':BAD,'good_ids':GOOD,'definition':'error increment = norm of consecutive position-error vector difference after established +37.5 ms timestamp alignment; event frame and +1/+2 frame associations. Per-flight Q90 normalization. Descriptive association, not causation. Covdiagonal is frame-native diag(Pm) instrument proxy; no covariance propagation/camera-origin transform, so not NEES/NIS. Event definitions use S counters (gate>0 or att>tri, map_match, map_accept, KLT fail), T anchor count increase, and live-track decrease.',
'groups':{},'flights':rows}
for group in ('bad','good'):
 rr=[r for r in rows if r['group']==group]
 summary['groups'][group]={'flights':len(rr),'median_error_increment_q90':float(np.median([r['error_increment_q90'] for r in rr])), 'events':{}}
 for ev in rr[0]['events']:
  summary['groups'][group]['events'][ev]={}
  for lag in ('0','1','2'):
   vals=[r['events'][ev][lag]['q90_normalized_median'] for r in rr if r['events'][ev][lag]['q90_normalized_median'] is not None]
   refs=[r['events'][ev][lag]['non_event_q90_normalized_median'] for r in rr if r['events'][ev][lag]['non_event_q90_normalized_median'] is not None]
   counts=sum(r['events'][ev][lag]['n'] for r in rr)
   summary['groups'][group]['events'][ev][lag]={'flights_with_events':len(vals),'total_event_frames':counts,'median_within_flight_q90_ratio':float(np.median(vals)) if vals else None,'non_event_median_within_flight_q90_ratio':float(np.median(refs)) if refs else None}
(OUT/'event_increment_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({g:summary['groups'][g] for g in ('bad','good')},indent=2))
