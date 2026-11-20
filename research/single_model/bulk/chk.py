import sys, glob, numpy as np
sys.argv=['x']
from research.single_model.bulk import decomp as D
from viobench.tools.runner.metrics import umeyama_sim3
import json
R = json.load(open('research/single_model/bulk/decomp_fresh_fe2_fbh.json'))
ate = np.array([r['ate'] for r in R]); q25,q75=np.percentile(ate,[25,75])
eps=[r['ep'] for r in R if q25<=r['ate']<=q75][:60]
res=[]
for ep in eps:
    p = glob.glob(f'{D.EV}/*/{ep}/report/logs/*/estimate.tum')[0]
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.runner.score import load_estimates
    from viobench.tools.runner.metrics import fill_missing_states
    e = read_episode(f'{D.POOL}/{ep}.zip', frames='none'); t=np.asarray(e.frame_times); G=np.asarray(e.ground_truth_state()); E=fill_missing_states(load_estimates(p,t))
    pe,pg=E[:,:3],G[:,:3]
    s,Rm,tt = umeyama_sim3(pe,pg)
    # SE3 (scale forced 1): rotation + translation
    mu_e,mu_g=pe.mean(0),pg.mean(0); H=(pe-mu_e).T@(pg-mu_g); U,S,Vt=np.linalg.svd(H); d=np.sign(np.linalg.det(Vt.T@U.T)); Rr=Vt.T@np.diag([1,1,d])@U.T
    se3=D.rate((Rr@(pe-mu_e).T).T+mu_g,pg)
    # rotation-only about origin
    H0=pe.T@pg; U,S,Vt=np.linalg.svd(H0); d=np.sign(np.linalg.det(Vt.T@U.T)); R0=Vt.T@np.diag([1,1,d])@U.T
    ro=D.rate((R0@pe.T).T,pg)
    ang=np.degrees(np.arccos(np.clip((np.trace(R0)-1)/2,-1,1)))
    # position-level derotation by instantaneous Rerr
    res.append((D.rate(pe,pg),se3,ro,ang))
res=np.array(res); print('ate, SE3 aligned, rot-only-origin aligned, rot angle deg:',res.mean(0), np.median(res,0))
