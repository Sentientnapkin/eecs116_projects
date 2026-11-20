import sys, glob, json, numpy as np
sys.argv=['x','bk_fresh_i2map']
from research.single_model.bulk import decomp as D
from multiprocessing import Pool
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
def one(ep):
    p = glob.glob(f'{D.EV}/*/{ep}/report/logs/*/estimate.tum')[0]
    e = read_episode(f'{D.POOL}/{ep}.zip', frames='none'); t=np.asarray(e.frame_times); G=np.asarray(e.ground_truth_state()); E=fill_missing_states(load_estimates(p,t))
    # camera-frame twist: compare speeds and direction angle
    out=[]
    for a,b in ((3,6),(6,10),(10,20),(20,40),(40,60)):
        i,j=int(a*20),int(b*20); vg=G[i:j,7:10]; ve=E[i:j,7:10]
        sg=np.linalg.norm(vg,axis=1); se=np.linalg.norm(ve,axis=1); m=sg>0.5
        if m.sum()<5: out.append((np.nan,)*4); continue
        cosang=np.sum(vg[m]*ve[m],1)/(sg[m]*se[m]+1e-9)
        out.append((np.mean(se[m]/sg[m]), np.sqrt(np.mean((se[m]-sg[m])**2)), np.degrees(np.mean(np.arccos(np.clip(cosang,-1,1)))), np.mean(se[m]-sg[m])))
    return np.array(out)
if __name__=='__main__':
    R=json.load(open('research/single_model/bulk/decomp_bk_fresh_i2map.json')); tab={r['episode']:r for r in json.load(open('research/single_model/fresh/table_fe2_fbh.json'))}
    ate=np.array([r['ate'] for r in R]); q25,q75=np.percentile(ate,[25,75])
    eps=[r['ep'] for r in R if q25<=r['ate']<=q75]
    with Pool(12) as p: rr=np.array(p.map(one,eps))
    print('window | mean speed ratio est/true | rms speed err m/s | mean direction angle deg | mean signed speed err (i2map typical flights)')
    for k,(a,b) in enumerate(((3,6),(6,10),(10,20),(20,40),(40,60))): print((a,b), np.round(np.nanmean(rr[:,k],0),3))
