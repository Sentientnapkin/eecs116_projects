"""T6: gyro-conditioned start-velocity prior (truth-only falsification, 5-fold CV over 363 mid-start flights, camera-0 axes)."""
import sys,pickle; sys.path.insert(0,'research/single_model/simstruct')
from load import *
rows=pickle.load(open('research/single_model/simstruct/t5.pkl','rb'))
Rcb=np.array([[0,-1,0],[0,0,-1],[1,0,0]],float)
VC=np.array([Rcb@r['vb'] for r in rows]); G=np.array([r['gyro'] for r in rows]); wz=G[:,2]
n=len(rows); rng=np.random.default_rng(0); perm=rng.permutation(n); folds=np.array_split(perm,5)
def feats(kind):
    a=np.abs(wz); s=np.sign(wz); sat=np.minimum(a/0.65,1)
    if kind=='const': return np.ones((n,1))
    if kind=='lin': return np.c_[np.ones(n),wz]
    if kind=='sat': return np.c_[np.ones(n),wz,sat]
    if kind=='sat2': return np.c_[np.ones(n),wz,sat,sat**2]
def cv(kind):
    X=feats(kind); P=np.zeros((n,3))
    for f in folds:
        tr=np.setdiff1d(np.arange(n),f)
        B=np.linalg.lstsq(X[tr],VC[tr],rcond=None)[0]; P[f]=X[f]@B
    return P
base=np.tile([0,0,0.9],(n,1))
def rep(name,P):
    e=VC-P; print(f'{name:34s} rmse per axis x,y,z = {np.sqrt((e**2).mean(0)).round(3)}  total |err| mean {np.linalg.norm(e,axis=1).mean():.3f}  rms {np.sqrt((np.linalg.norm(e,axis=1)**2).mean()):.3f}')
rep('current prior mean (0,0,0.9)',base)
rep('zero velocity',np.zeros((n,3)))
for k in ('const','lin','sat','sat2'): rep('CV linear model on '+k,cv(k))
X=feats('sat'); B=np.linalg.lstsq(X,VC,rcond=None)[0]; print('full-fit coefficients [const, wz, sat] per axis (x,y,z):\n',B.round(3))
# residual std per axis in saturated vs unsat groups
P=cv('sat'); e=VC-P
for name,m in (('|wz|<0.15',np.abs(wz)<0.15),('0.15-0.45',(np.abs(wz)>=0.15)&(np.abs(wz)<0.45)),('>0.45',np.abs(wz)>=0.45)):
    print(f'  residual std {name:10s} n={m.sum():3d}: x {e[m,0].std():.2f} y {e[m,1].std():.2f} z {e[m,2].std():.2f}   raw std x {VC[m,0].std():.2f} y {VC[m,1].std():.2f} z {VC[m,2].std():.2f}')
# Gaussian NLL comparison per flight (diag cov = per-axis residual var): current vs conditional
def nll(P,sd): z=(VC-P)/sd; return (0.5*z**2+np.log(sd)).sum(1).mean()
print('mean NLL: current (0,0,.9;.5,.35,.6) %.3f ; fitted-const %.3f ; gyro-conditional (CV) %.3f'%(nll(base,np.array([.5,.35,.6])),nll(cv('const'),VC.std(0)),nll(P,e.std(0))))
# the tilt-accel: also roll/pitch rates vs vc_y?
for j,nm in enumerate(('wx','wy')):
    print('corr(%s, vc_x/vc_y/vc_z) ='%nm,[np.corrcoef(G[:,j],VC[:,i])[0,1].round(2) for i in range(3)])
