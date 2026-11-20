import sys, glob, json, numpy as np
sys.argv=['x','fresh_fe2_fbh']
from research.single_model.bulk import decomp as D
from multiprocessing import Pool
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
def one(ep):
    p = glob.glob(f'{D.EV}/*/{ep}/report/logs/*/estimate.tum')[0]
    e = read_episode(f'{D.POOL}/{ep}.zip', frames='none'); t=np.asarray(e.frame_times); G=np.asarray(e.ground_truth_state()); E=fill_missing_states(load_estimates(p,t))
    pe,pg=E[:,:3],G[:,:3]; err=pe-pg; n=len(t); k=20
    rows=[]
    for i in range(100,n-k,k):    # skip first 5 s
        de=err[i+k]-err[i]
        v=np.linalg.norm(pg[i+k]-pg[i])/1.0
        w=np.mean(np.linalg.norm(G[i:i+k,10:13],axis=1))
        vv=G[i:i+k,7:10]; a=np.linalg.norm(vv[-1]-vv[0])
        rows.append((float(de@de), v, w, a, float(np.linalg.norm(err[i]))))
    return rows
if __name__=='__main__':
    R=json.load(open('research/single_model/bulk/decomp_fresh_fe2_fbh.json')); ate=np.array([r['ate'] for r in R]); q25,q75=np.percentile(ate,[25,75])
    eps=[r['ep'] for r in R if q25<=r['ate']<=q75]
    with Pool(12) as p: rr=p.map(one,eps)
    X=np.array([x for r in rr for x in r]); print(X.shape)
    y=X[:,0]; sp=X[:,1]; w=X[:,2]; a=X[:,3]
    print('mean de2 per s', y.mean(), 'by speed quartile:'); 
    for lab,v in (('speed',sp),('|w|',w),('|dv|',a)):
        qs=np.percentile(v,[0,25,50,75,100]); print(lab, [round(float(y[(v>=qs[i])&(v<=qs[i+1])].mean()),5) for i in range(4)], 'edges', np.round(qs,2))
    A=np.column_stack([sp**2,w**2,a**2,np.ones_like(y)]); c=np.linalg.lstsq(A,y,rcond=None)[0]; print('coef speed^2,w^2,dv^2,const',c, 'R2', 1-((A@c-y)**2).sum()/((y-y.mean())**2).sum())
    print('corr(de2, speed, w, dv):',[round(float(np.corrcoef(y,v)[0,1]),3) for v in (sp,w,a)])
