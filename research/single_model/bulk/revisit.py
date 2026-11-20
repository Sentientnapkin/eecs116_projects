import sys, glob, json, numpy as np
sys.argv=['x','fresh_fe2_fbh']
from research.single_model.bulk import decomp as D
from multiprocessing import Pool
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import poses_to_matrices
def one(ep):
    e = read_episode(f'{D.POOL}/{ep}.zip', frames='none'); G=np.asarray(e.ground_truth_state())
    Rg=poses_to_matrices(G)[:,:3,:3]; p=G[:,:3]; z=Rg[:,:,2]; n=len(p)
    out=[]
    for dist,ang in ((0.5,25),(1.0,35),(1.5,50)):
        c=np.cos(np.radians(ang)); hit=0; tot=0
        for i in range(200,n,4):   # clone-rate, after 10 s
            j=slice(0,i-100)       # >= 5 s old
            m=(np.linalg.norm(p[j]-p[i],axis=1)<dist)&(z[j]@z[i]>c)
            hit+=m.any(); tot+=1
        out.append(hit/tot)
    return out
if __name__=='__main__':
    R=json.load(open('research/single_model/bulk/decomp_fresh_fe2_fbh.json')); ate=np.array([r['ate'] for r in R]); q25,q75=np.percentile(ate,[25,75])
    eps=[r['ep'] for r in R if q25<=r['ate']<=q75][:120]
    with Pool(8) as p: rr=np.array(p.map(one,eps))
    print('fraction of frames (after 10 s) with a >=5 s older view within (0.5 m,25deg),(1 m,35deg),(1.5 m,50deg):', rr.mean(0).round(3))
