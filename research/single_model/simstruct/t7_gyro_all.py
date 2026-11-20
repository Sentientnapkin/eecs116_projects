"""T7: multi-feature gyro(+|f|) conditioning of start velocity and tilt (CV), mid starts, camera-0 axes."""
import sys,pickle; sys.path.insert(0,'research/single_model/simstruct')
from load import *
rows=pickle.load(open('research/single_model/simstruct/t5.pkl','rb'))
Rcb=np.array([[0,-1,0],[0,0,-1],[1,0,0]],float)
VC=np.array([Rcb@r['vb'] for r in rows]); UC=np.array([Rcb@r['up_b'] for r in rows]); G=np.array([r['gyro'] for r in rows]); F=np.array([r['f'] for r in rows])
n=len(rows); wx,wy,wz=G.T; sat=np.minimum(np.abs(wz)/0.65,1)
# camera-axis gyro: w_c = Rcb w_b  (x right=-wy, y down=-wz, z fwd=wx)
rng=np.random.default_rng(1); perm=rng.permutation(n); folds=np.array_split(perm,5)
def cv(X,Y):
    P=np.zeros_like(Y)
    for f in folds:
        tr=np.setdiff1d(np.arange(n),f); B=np.linalg.lstsq(X[tr],Y[tr],rcond=None)[0]; P[f]=X[f]@B
    return P
sets={'const':np.ones((n,1)),'wz,sat':np.c_[np.ones(n),wz,sat],'+wy':np.c_[np.ones(n),wz,sat,wy],'+wx,wy':np.c_[np.ones(n),wz,sat,wx,wy],
      '+wx,wy,|wy|,|wx|':np.c_[np.ones(n),wz,sat,wx,wy,np.abs(wx),np.abs(wy)],'+fz':np.c_[np.ones(n),wz,sat,wx,wy,F[:,2]]}
print('VELOCITY (cam axes x,y,z) CV rmse   [current const-prior rmse .497 .336 .761]')
for k,X in sets.items():
    e=VC-cv(X,VC); print(f'  {k:18s} {np.sqrt((e**2).mean(0)).round(3)}  3D rms {np.sqrt((np.linalg.norm(e,axis=1)**2).mean()):.3f}')
print('TILT (up vector in cam axes: x,z comps) CV rmse   [const rmse %.3f %.3f]'%(UC[:,0].std(),UC[:,2].std()))
for k,X in sets.items():
    e=UC-cv(X,UC); print(f'  {k:18s} x {np.sqrt((e[:,0]**2).mean()):.3f}  z {np.sqrt((e[:,2]**2).mean()):.3f}')
B=np.linalg.lstsq(sets['+wx,wy'],VC,rcond=None)[0]; print('coef [1,wz,sat,wx,wy] for vc x,y,z:\n',B.round(3).T)
# physical reading: forward speed vs pitch rate: 
print('corr(wy, vc_z) %.2f ; corr(wx, vc_x) %.2f ; corr(wy,UC_z) %.2f corr(wx,UC_x) %.2f'%(np.corrcoef(wy,VC[:,2])[0,1],np.corrcoef(wx,VC[:,0])[0,1],np.corrcoef(wy,UC[:,2])[0,1],np.corrcoef(wx,UC[:,0])[0,1]))
