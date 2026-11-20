"""T8: continuous version: body-frame lateral velocity vs yaw rate (all frames t>2 s, 80 flights; cross-flight CV by flight)."""
import sys,pickle; sys.path.insert(0,'research/single_model/simstruct')
from load import *
R=pickle.load(open('research/single_model/simstruct/t2.pkl','rb'))
ids=sorted(R); rng=np.random.default_rng(0); rng.shuffle(ids)
def data(i):
    r=R[i]; m=(r['t']>2.0)[::10]
    vb=np.einsum('nji,nj->ni',r['Rm'],r['v'])[::10][m]; wz=r['wb'][::10][m][:,2]; wxy=r['wb'][::10][m][:,:2]
    return vb,wz,wxy
D={i:data(i) for i in ids}
fold=lambda k: ids[k::5]
def build(vb,wz,wxy,kind):
    sp=np.linalg.norm(vb[:,:2],axis=1); sat=np.minimum(np.abs(wz)/0.65,1)
    if kind=='const': return np.ones((len(wz),1))
    if kind=='wz': return np.c_[np.ones(len(wz)),wz]
    if kind=='wz*|v|': return np.c_[np.ones(len(wz)),wz,wz*sp]
    if kind=='wz,sat,wy': return np.c_[np.ones(len(wz)),wz,sat,wxy[:,1],wxy[:,0]]
for tgt,j,name in ((1,1,'vb_y (lateral, body left)'),(0,0,'vb_x (forward)'),(2,2,'vb_z (vertical)')):
    print('target',name)
    for kind in ('const','wz','wz*|v|','wz,sat,wy'):
        err=[];ys=[]
        for k in range(5):
            te=fold(k); tr=[i for i in ids if i not in te]
            X=np.vstack([build(*D[i],kind) for i in tr]); y=np.concatenate([D[i][0][:,j] for i in tr])
            b=np.linalg.lstsq(X,y,rcond=None)[0]
            for i in te: err.append(D[i][0][:,j]-build(*D[i],kind)@b); ys.append(D[i][0][:,j])
        err=np.concatenate(err); ys=np.concatenate(ys)
        print(f'   {kind:12s} resid rms {np.sqrt((err**2).mean()):.3f}   (raw rms {np.sqrt((ys**2).mean()):.3f})  R2 {1-(err**2).sum()/(ys**2).sum():.3f}')
