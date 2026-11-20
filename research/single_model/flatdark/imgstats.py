"""Per-flight pixel statistics + per-cell Shi-Tomasi (the C detector's score) at several thresholds. usage: imgstats.py ep [ep...]"""
import sys,json,numpy as np,cv2
sys.path.insert(0,'/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
B='/data/backups/rganapa/Sebastian/gen/raw-fast/bench/'
def score_map(g):
    g=g.astype(np.float32)
    gx=np.zeros_like(g);gy=np.zeros_like(g)
    gx[:,1:-1]=g[:,2:]-g[:,:-2]; gy[1:-1]=g[2:]-g[:-2]
    k=np.ones((3,3),np.float32)
    sxx=cv2.filter2D(gx*gx,-1,k);syy=cv2.filter2D(gy*gy,-1,k);sxy=cv2.filter2D(gx*gy,-1,k)
    return 0.5*(sxx+syy)-np.sqrt(0.25*(sxx-syy)**2+sxy**2)
def cellmax(S):
    S=S[:240,:320].copy(); S[:7]=0;S[-7:]=0;S[:,:7]=0;S[:,-7:]=0
    return S.reshape(6,40,10,32).max(axis=(1,3))
def stats(ep,n=12):
    e=read_episode(B+ep+'.zip'); N=e.num_frames
    out=[]
    for i in np.linspace(5,N-5,n).astype(int):
        f=e.frames[i]; f=cv2.resize(f,(320,240),interpolation=cv2.INTER_AREA)
        g=f.astype(np.float32).mean(2)
        lap=cv2.Laplacian(g,cv2.CV_32F)
        noise=1.4826*np.median(np.abs(lap-np.median(lap)))/np.sqrt(20)  # lap noise gain sqrt(20)
        cm=cellmax(score_map(g))
        out.append(dict(mean=g.mean(),std=g.std(),noise=noise,c1000=(cm>1000).sum(),c500=(cm>500).sum(),c250=(cm>250).sum(),c100=(cm>100).sum(),
                        sat=(g>=250).mean(),blk=(g<=5).mean()))
    return {k:float(np.mean([o[k] for o in out])) for k in out[0]}
if __name__=='__main__':
    for ep in sys.argv[1:]:
        s=stats(ep); print(ep,' '.join(f'{k}={v:.2f}' for k,v in s.items()),flush=True)
