import json, sys; sys.path.insert(0,'.')
import numpy as np
from research.single_model.run_variant import OUT
rows=json.load(open('research/single_model/gate/series_search.json'))
THR=2.0
def dec(r,k):
    d=[x for x in r['d'][:k] if x>=0]
    if len(d)<min(k,2) and k>1: return 'undec'
    if not d: return 'undec'
    return 'REL' if max(d)<THR else 'hold'
print('## Confusion of the gate decision (rule: release iff max over clone pairs so far < %.1f px), search slice, per flight'%THR)
for k,tm in ((1,'0.25'),(2,'0.45'),(3,'0.65'),(5,'1.05')):
    print(f'\ndecision after pair {k} (t~{tm} s); REL=release prior, hold=keep, undec=<10 matched features so far (prior stays)')
    print('| group | n | REL | hold | undec |'); print('|---|---|---|---|---|')
    for lab,sel in [('static label',lambda r:r['start']=='static'),('mid label',lambda r:r['start']=='mid')]+[(f'mid, true |v| {lo}-{hi} m/s',(lambda lo,hi:lambda r:r['start']=='mid' and lo<=r['sp05']<hi)(lo,hi)) for lo,hi in ((0,0.2),(0.2,0.5),(0.5,1.0),(1.0,9))]:
        R=[r for r in rows if sel(r)]; c=[dec(r,k) for r in R]
        print(f'| {lab} | {len(R)} | {c.count("REL")} | {c.count("hold")} | {c.count("undec")} |')
print('\nstart speed = mean |v| over t<=0.45 s from truth (twist rows, camera axes, norm is frame invariant); static label: all 0.04 m/s')
print('mid start-speed percentiles 0/10/50/90/100:',np.percentile([r['sp05'] for r in rows if r['start']=='mid'],[0,10,50,90,100]).round(2))
print('\nreleased mid flights (decision at pair 2): start speed, d1,d2')
for r in rows:
    if r['start']=='mid' and dec(r,2)=='REL': print(' ',r['e'],'speed %.2f'%r['sp05'],'d',[round(x,2) for x in r['d'][:3]])
# disparity vs speed
v=[(r['spk'][1],r['d'][1]) for r in rows if r['start']=='mid' and r['d'][1]>=0]
v=np.array(v); print('\nmid: corr(d pair2, speed) %.2f ; median d/speed ratio %.1f px per m/s'%(np.corrcoef(v[:,0],v[:,1])[0,1],np.median(v[:,1]/np.maximum(v[:,0],0.05))))
# static tails
S=np.array([x for r in rows if r['start']=='static' for x in r['d'][:5] if x>=0]); print('static pairs 1-5 (hover) n=%d mean %.2f sd %.2f max %.2f; (thr-mean)/sd = %.1f'%(len(S),S.mean(),S.std(),S.max(),(THR-S.mean())/S.std()))
# per-arm effect on mid by speed bin
def load(n): return {x['e']:x for x in json.loads((OUT/f'{n}/report.json').read_text())['rows_visible']}
f0=load('final_f0'); a=load('gate_a_h20')
print('\nrow-level change a_h20 vs f0 (flights where ATE differs):')
for e in a:
    if abs(a[e]['new']-f0[e]['new'])>1e-9: 
        r=[x for x in rows if x['e']==e]; sp=r[0]['sp05'] if r else float('nan')
        print(f"  {e} {a[e]['start']} f0 {f0[e]['new']:.3f} gate {a[e]['new']:.3f} speed {sp:.2f} fold {a[e]['fold']}")
