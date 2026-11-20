import sys,glob,json,numpy as np
sys.path.insert(0,'/data/backups/rganapa/Sebastian/eecs116_projects')
from research import wasm_eval as W

def q2m(q):
    q=np.atleast_2d(q); x,y,z,w=q.T; n=np.sqrt(x*x+y*y+z*z+w*w); x,y,z,w=x/n,y/n,z/n,w/n
    return np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],1).reshape(-1,3,3)
def m2q(M):
    out=[]
    for m in M:
        t=np.trace(m)
        if t>0:
            s=np.sqrt(t+1)*2; q=[(m[2,1]-m[1,2])/s,(m[0,2]-m[2,0])/s,(m[1,0]-m[0,1])/s,0.25*s]
        else:
            i=int(np.argmax(np.diag(m))); j=(i+1)%3; k=(i+2)%3
            s=np.sqrt(m[i,i]-m[j,j]-m[k,k]+1)*2; q=[0,0,0,0]
            q[i]=0.25*s; q[j]=(m[j,i]+m[i,j])/s; q[k]=(m[k,i]+m[i,k])/s; q[3]=(m[k,j]-m[j,k])/s
        out.append(q)
    return np.array(out)
R='/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/'
POOL='/data/backups/rganapa/Sebastian/tmp/fresh_pool/'
_cache={}
def ep_data(ep):
    if ep not in _cache:
        e=W.read_episode(POOL+ep+'.zip',frames='none'); _cache[ep]=(e,e.ground_truth_state())
        if len(_cache)>40: _cache.pop(next(iter(_cache)))
    return _cache[ep]
def est(name,ep):
    e,_=ep_data(ep)
    f=glob.glob(R+f'fresh_mh_{name}/eval/*/{ep}/report/logs/*/estimate.tum')[0]
    return W.load_estimates(f,e.frame_times)
def ate(ep,E):
    e,tr=ep_data(ep); m=W.evaluate_trajectory(tr,E,e.frame_times)
    return m.ate_rmse if hasattr(m,'ate_rmse') else m['ate_rmse']
def splice(Ea,Eb,k):
    """output Ea[:k], then b's motion relative to frame k carried on a's pose at k"""
    out=Ea.copy()
    Ra=q2m(Ea[k,3:7])[0]; Rb=q2m(Eb[k,3:7])[0]; D=Ra@Rb.T
    out[k:,0:3]=Ea[k,0:3]+(Eb[k:,0:3]-Eb[k,0:3])@D.T
    out[k:,3:7]=m2q(D@q2m(Eb[k:,3:7]))
    out[k:,7:]=Eb[k:,7:]
    return out
