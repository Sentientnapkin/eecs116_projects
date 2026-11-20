import sys, glob, json, numpy as np
sys.argv=['x','bk_fresh_i2map']
from research.single_model.bulk import decomp as D
from multiprocessing import Pool
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
def one(ep):
    p = glob.glob(f'{D.EV}/*/{ep}/report/logs/*/estimate.tum')[0]
    e = read_episode(f'{D.POOL}/{ep}.zip', frames='none'); t=np.asarray(e.frame_times); G=np.asarray(e.ground_truth_state()); E=fill_missing_states(load_estimates(p,t))
    err=E[:,:3]-G[:,:3]
    # velocity in cam0 frame
    Rg=poses_to_matrices(G)[:,:3,:3]; Re=poses_to_matrices(E)[:,:3,:3]
    vg=np.einsum('nij,nj->ni',Rg,G[:,7:10]); ve=np.einsum('nij,nj->ni',Re,E[:,7:10])
    out=[]
    for ts in range(0,10):
        i=int(ts*20); out.append((np.linalg.norm(vg[i]), np.linalg.norm(ve[i]-vg[i]), np.linalg.norm(err[i]), np.linalg.norm(vg[min(i+20,len(t)-1)]-vg[i])))
    return np.array(out)
if __name__=='__main__':
    R=json.load(open('research/single_model/bulk/decomp_bk_fresh_i2map.json')); tab={r['episode']:r for r in json.load(open('research/single_model/fresh/table_fe2_fbh.json'))}
    ate=np.array([r['ate'] for r in R]); q25,q75=np.percentile(ate,[25,75])
    eps=[r['ep'] for r in R if q25<=r['ate']<=q75 and tab[r['ep']]['start']=='static']
    with Pool(12) as p: rr=np.array(p.map(one,eps))
    print(len(eps)); print('t(s)  truth speed | vel err | pos err | |dv| over next 1s  (typical static, mean)')
    for ts in range(10): print(ts, np.round(rr[:,ts].mean(0),3))
