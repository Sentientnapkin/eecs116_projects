"""Classify the safe-guard held-out failures; truth is diagnostic only."""
import json
from pathlib import Path
import numpy as np
from research.guard_fusion.traj import load_episode
from research.guard_fusion.guards import replay,GuardConfig, SOURCE_NAMES

def main():
    p=json.load(open('research/results/eval/guard-fusion/v2-safe/summary-s217.json'))
    configs={c['name']:c for c in p['protocol']['candidates']}
    out=[]
    for row in p['rows']:
     if row['cv_ate']<=5: continue
     data=load_episode(episode=row['episode']); t=data['t']; src=data['sources']; truth=data['truth']
     T,info=replay(t,src,GuardConfig(**configs[row['cv_arm']]),True)
     err=np.linalg.norm(T[:,:3,3]-truth[:,:3],axis=1)
     agreement=info['agree']; w=info['weights']; dominant=np.argmax(w,axis=1)
     switches=np.r_[False,np.any(np.diff(w,axis=0)!=0,axis=1)]
     near_switch=np.zeros(len(t),bool)
     for k in np.where(switches)[0]: near_switch|=(t>=t[k])&(t<=t[k]+1)
     squared=err**2
     def fraction(mask):return float(squared[mask].sum()/squared.sum())
     best=min(row['singles'],key=row['singles'].get)
     classification='both_VIOs_bad' if min(row['singles'][s] for s in ('vins','openvins'))>3 else 'wrong_VIO_selection'
     if fraction(near_switch)>.5: classification+='; transition_dominated'
     if row['singles']['n2']>5: classification+='; learned_fallback_bad'
     out.append({'episode':row['episode'],'cv_ate':row['cv_ate'],'best_single':best,'singles':row['singles'],
      'classification':classification,'weight_change_count':int(switches.sum()),'VIO_agreement_fraction':float(agreement.mean()),
      'source_weight_mean':dict(zip(SOURCE_NAMES,w.mean(axis=0).tolist())),
      'squared_error_share_during_VIO_agreement':fraction(agreement),
      'squared_error_share_within_1s_switch':fraction(near_switch),
      'max_output_step_m':float(np.max(np.linalg.norm(np.diff(T[:,:3,3],axis=0),axis=1)))})
    Path('research/results/eval/guard-fusion/v2-safe/failure-classification.json').write_text(json.dumps(out,indent=2)+'\n')
    for r in out: print(r['episode'],round(r['cv_ate'],3),r['classification'],r['source_weight_mean'])

if __name__=='__main__':
    main()
