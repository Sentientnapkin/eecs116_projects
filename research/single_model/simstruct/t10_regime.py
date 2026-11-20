"""T10: regime-wise (|gyro_z| aligned/mid/saturated) start-velocity prior, CV over 363 mid starts; compare NLL and RMSE with the adopted prior."""
import sys,pickle; sys.path.insert(0,'research/single_model/simstruct')
from load import *
rows=pickle.load(open('research/single_model/simstruct/t5.pkl','rb'))
Rcb=np.array([[0,-1,0],[0,0,-1],[1,0,0]],float)
VC=np.array([Rcb@r['vb'] for r in rows]); G=np.array([r['gyro'] for r in rows]); wz=G[:,2]; wy=G[:,1]; wx=G[:,0]; n=len(rows)
reg=np.where(np.abs(wz)<0.15,0,np.where(np.abs(wz)<0.45,1,2))
X=np.c_[np.ones(n),wz,np.minimum(np.abs(wz)/0.65,1),wx,wy]
rng=np.random.default_rng(2); perm=rng.permutation(n); folds=np.array_split(perm,5)
P=np.zeros((n,3)); S=np.zeros((n,3))
for f in folds:
    tr=np.setdiff1d(np.arange(n),f); B=np.linalg.lstsq(X[tr],VC[tr],rcond=None)[0]
    res=VC[tr]-X[tr]@B
    P[f]=X[f]@B
    for g in range(3):
        sd=res[reg[tr]==g].std(0); S[f[reg[f]==g]]=sd
nll=lambda P,S:((0.5*((VC-P)/S)**2+np.log(S)).sum(1)).mean()
cur=np.tile([0,0,.9],(n,1)); cs=np.tile([.5,.35,.6],(n,1))
print('mean per-flight NLL (lower better, diag Gaussian):')
print('  adopted (0,0,.9; .5,.35,.6)        %.3f   rmse3D %.3f'%(nll(cur,cs),np.sqrt((np.linalg.norm(VC-cur,axis=1)**2).mean())))
print('  gyro-regime-conditional (CV)       %.3f   rmse3D %.3f'%(nll(P,S),np.sqrt((np.linalg.norm(VC-P,axis=1)**2).mean())))
z=(VC-P)/S; print('  calibration of conditional model: mean z^2 per axis',(z**2).mean(0).round(2),' frac |z|>2 per axis',(np.abs(z)>2).mean(0).round(3))
zc=(VC-cur)/cs; print('  adopted prior calibration: mean z^2',(zc**2).mean(0).round(2),' frac |z|>2',(np.abs(zc)>2).mean(0).round(3))
for g,name in enumerate(('aligned |wz|<.15','mid','saturated >=.45')):
    m=reg==g; print(f'  {name:18s} n={m.sum():3d} fraction {m.mean():.2f}: rmse3D adopted {np.sqrt((np.linalg.norm(VC[m]-cur[m],axis=1)**2).mean()):.2f} -> conditional {np.sqrt((np.linalg.norm(VC[m]-P[m],axis=1)**2).mean()):.2f}; sigma x,y,z {S[m][0].round(2)}')
# what is the cost of the 'wrong-direction' cases: worst-case errors
e=np.linalg.norm(VC-cur,axis=1); e2=np.linalg.norm(VC-P,axis=1); print('p90/p99 |v err|: adopted %.2f %.2f ; conditional %.2f %.2f'%(*np.percentile(e,[90,99]),*np.percentile(e2,[90,99])))
