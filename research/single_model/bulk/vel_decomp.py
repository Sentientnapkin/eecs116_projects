"""Integrated-increment-error decomposition in the local (truth-motion) frame: along-track / lateral-horizontal / vertical."""
import sys, glob, json, numpy as np
sys.argv=['x', sys.argv[1] if len(sys.argv)>1 else 'fresh_fe2_fbh']
from research.single_model.bulk import decomp as D
from multiprocessing import Pool
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
def one(ep):
    p = glob.glob(f'{D.EV}/*/{ep}/report/logs/*/estimate.tum')[0]
    e = read_episode(f'{D.POOL}/{ep}.zip', frames='none'); t=np.asarray(e.frame_times); G=np.asarray(e.ground_truth_state()); E=fill_missing_states(load_estimates(p,t))
    pe,pg=E[:,:3],G[:,:3]; n=len(t)
    Rbc = np.asarray(e.T_body_camera)[:3, :3]
    from viobench.tools.geometry import poses_to_matrices
    Rg = poses_to_matrices(G)[:, :3, :3]
    imu = np.asarray(e.imu); idx=np.clip(np.searchsorted(t, imu[:,0]),0,n-1)
    up=np.einsum('nij,nj->ni',Rg[idx], imu[:,1:4]@Rbc).mean(0); up/=np.linalg.norm(up)
    dg=np.diff(pg,axis=0); de=np.diff(pe,axis=0); d=de-dg
    # local direction: horizontal truth motion smoothed over 2 s
    k=np.ones(41)/41
    sm=np.column_stack([np.convolve(dg[:,j],k,'same') for j in range(3)])
    sh=sm-(sm@up)[:,None]*up; nn=np.linalg.norm(sh,axis=1)
    ok=nn>0.01
    ex=np.where(ok[:,None], sh/np.maximum(nn,1e-9)[:,None], np.array([1.,0,0]))
    # for non-moving periods use previous direction (keep simple: basis arbitrary orth to up)
    ey=np.cross(up,ex)
    comp=[np.einsum('ni,ni->n',d,ex), np.einsum('ni,ni->n',d,ey), d@up]
    out={'ep':ep,'ate':D.rate(pe,pg)}
    basis=[ex,ey,np.broadcast_to(up,ex.shape)]
    for name,c,b in zip(('along','lat','vert'),comp,basis):
        corr=np.cumsum(c[:,None]*b,0); pp=pe.copy(); pp[1:]-=corr
        out['o_'+name]=D.rate(pp,pg)
        out['rms_'+name]=float(np.sqrt(np.mean(c**2))/0.05)   # m/s
        out['bias_'+name]=float(np.mean(c)/0.05)
    out['o_alonglat']=None
    c=comp; corr=np.cumsum(c[0][:,None]*ex+c[1][:,None]*ey,0); pp=pe.copy(); pp[1:]-=corr; out['o_horiz']=D.rate(pp,pg)
    sp=np.linalg.norm(dg,axis=1)/0.05
    out['speed']=float(sp.mean())
    # slow-motion fraction (hover-ish segments)
    out['frac_slow']=float((sp<0.2).mean())
    # speed-ratio over 2 s windows: |dpe|/|dpg|
    return out
if __name__=='__main__':
    R=json.load(open(f'research/single_model/bulk/decomp_{D.RUN}.json'))
    ate=np.array([r['ate'] for r in R]); q25,q75=np.percentile(ate,[25,75])
    eps=[r['ep'] for r in R if q25<=r['ate']<=q75]
    with Pool(12) as p: rows=p.map(one,eps)
    json.dump(rows,open('research/single_model/bulk/veldecomp.json','w'))
    for k in ('ate','o_along','o_lat','o_vert','o_horiz','rms_along','rms_lat','rms_vert','bias_along','bias_lat','bias_vert','speed','frac_slow'):
        v=np.array([r[k] for r in rows]); print(k, round(float(v.mean()),4), round(float(np.median(v)),4))
