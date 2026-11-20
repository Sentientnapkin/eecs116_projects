"""WP3: predeclared physical guards and late-origin substitution on saved streams.

All arms use past/current source states only. N2 origin substitution is a replay
of a future composite capability, never claimed to fix the standalone guest.
"""
import argparse, json, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from guard_fusion.traj import load_episode, list_episodes, DEFAULT_SELECTED, DEFAULT_RAW
from viobench.tools.geometry import matrices_to_poses
from viobench.tools.runner.metrics import evaluate_trajectory

def physical_guard(times, vio, n2=None, use_origin=False, max_speed=6., max_accel=12.):
    T=vio['T']; N=len(times); out=T.copy(); choices=np.zeros(N,dtype=np.int32)
    if n2 is not None and use_origin:
        out[:]=n2['T']
    previous_world_v=np.zeros(3); active=False
    for k in range(1,N):
        dt=float(times[k]-times[k-1]); ready=vio['init_s'] is not None and times[k]>=vio['init_s']-1e-6
        if not ready:
            if n2 is not None and use_origin: out[k]=n2['T'][k]
            continue
        raw_world_v=T[k,:3,:3]@vio['states'][k,7:10]
        d=T[k-1,:3,:3].T@(T[k,:3,3]-T[k-1,:3,3])
        bad=(not vio['valid'][k] or np.linalg.norm(raw_world_v)>max_speed or
             np.linalg.norm(raw_world_v-T[k-1,:3,:3]@vio['states'][k-1,7:10])/dt>max_accel or
             np.linalg.norm(d)/dt>max_speed)
        if use_origin and not active:
            # At first ready output retain N2's accumulated pose and only consume
            # VIO motion on the following frame. This is a causal origin switch.
            active=True; previous_world_v=raw_world_v if not bad else np.zeros(3)
            choices[k]=2; continue
        active=True
        if bad:
            choices[k]=1
            if n2 is not None:
                source=n2['T']; local_dR=source[k-1,:3,:3].T@source[k,:3,:3]
                d=source[k-1,:3,:3].T@(source[k,:3,3]-source[k-1,:3,3])
            else:
                local_dR=T[k-1,:3,:3].T@T[k,:3,:3]
                d=out[k-1,:3,:3].T@previous_world_v*dt
                previous_world_v*=np.exp(-dt)
        else:
            local_dR=T[k-1,:3,:3].T@T[k,:3,:3]
            previous_world_v=raw_world_v
        out[k,:3,3]=out[k-1,:3,3]+out[k-1,:3,:3]@d
        out[k,:3,:3]=out[k-1,:3,:3]@local_dR
    states=vio['states'].copy(); states[:,:7]=matrices_to_poses(out)
    # Saved replay is scored for position ATE; expose a causal velocity that
    # matches its published motion instead of retaining a rejected raw twist.
    for k in range(1,N):
        states[k,7:10] = out[k,:3,:3].T @ ((out[k,:3,3]-out[k-1,:3,3])/(times[k]-times[k-1]))
        if choices[k] and n2 is not None: states[k,10:13]=n2['states'][k,10:13]
    return states,choices

def one(job):
    selected,raw,name=job; e=load_episode(selected,raw,name); t=e['t']; s=e['sources']; truth=e['truth']
    arms={}; events={}
    for key in ['openvins','vins']:
        arms[key]=s[key]['raw_states']
        for label,backup,origin in [('physical',None,False),('physical_n2',s['n2'],False),('origin_n2',s['n2'],True)]:
            est,choice=physical_guard(t,s[key],backup,origin)
            arm=key+'_'+label; arms[arm]=est; events[arm]=int((choice==1).sum())
    return {'episode':name,'tags':e['tags'],'ate':{k:float(evaluate_trajectory(truth,v,t).ate_rmse) for k,v in arms.items()},'guard_frames':events}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--selected',default=str(DEFAULT_SELECTED)); p.add_argument('--raw',default=str(DEFAULT_RAW)); p.add_argument('--workers',type=int,default=24); p.add_argument('--out',required=True); a=p.parse_args()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    spec={'declared_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'max_speed':6.,'max_accel':12.,'arms':['physical','physical_n2','origin_n2'],'tuned':False,'metric':'mean_unaligned_ate_m'}
    pre=out/'predeclaration.json'
    if pre.exists(): raise FileExistsError(pre)
    pre.write_text(json.dumps(spec,indent=2)+'\n')
    with ProcessPoolExecutor(max_workers=min(32,a.workers)) as pool: rows=list(pool.map(one,[(a.selected,a.raw,n) for n in list_episodes(a.selected)]))
    summary={key:{'n':len(rows),'mean':float(np.mean([r['ate'][key] for r in rows])),'median':float(np.median([r['ate'][key] for r in rows])),'over_10m':sum(r['ate'][key]>10 for r in rows)} for key in rows[0]['ate']}
    (out/'replay.json').write_text(json.dumps({'spec':spec,'summary':summary,'rows':rows},indent=2)+'\n'); print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
