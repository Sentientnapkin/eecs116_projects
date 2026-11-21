"""Fit the P1 start-velocity regression (cam axes) from simstruct/t5.pkl on DEV scene folds 0-2 only; also all-data fit for comparison.
Prints C defines. Model: vc = B^T [1,wz,sat,wx,wy]; sigma per |wz| regime from residuals."""
import sys,pickle,json,hashlib; sys.path.insert(0,'research/single_model/simstruct')
import numpy as np
from pathlib import Path
RAW=Path('/data/backups/rganapa/Sebastian/gen/raw-fast/bench')
rows=pickle.load(open('research/single_model/simstruct/t5.pkl','rb'))
def fold(i):
    d=json.load(open(RAW/(i+'.json'))); return int(hashlib.sha256((d['catalog']+':'+d['scene']).encode()).hexdigest()[:8],16)%5
fo=np.array([fold(r['id']) for r in rows])
Rcb=np.array([[0,-1,0],[0,0,-1],[1,0,0]],float)
VC=np.array([Rcb@r['vb'] for r in rows]); G=np.array([r['gyro'] for r in rows]); wx,wy,wz=G.T
X=np.c_[np.ones(len(G)),wz,np.minimum(np.abs(wz)/0.65,1),wx,wy]
reg=np.where(np.abs(wz)<0.15,0,np.where(np.abs(wz)<0.45,1,2))
def fit(m):
    B=np.linalg.lstsq(X[m],VC[m],rcond=None)[0]; res=VC[m]-X[m]@B
    S=np.array([res[reg[m]==g].std(0) for g in range(3)]); return B,S
for name,m in (('dev',fo<=2),('all',fo<=3),('confirm(3)',fo==3)):
    B,S=fit(m); print(name,m.sum()); print(' B(5x3)=',B.T.round(3).tolist()); print(' S(reg x3)=',S.round(3).tolist())
    if name=='dev':
        Bd,Sd=B,S
te=fo>=3; P=X[te]@Bd; e=VC[te]-P; c=VC[te]-np.array([0,0,.9]); print('confirm folds3 rows',te.sum(),'3D rms conditional(dev fit)',np.sqrt((e**2).sum(1).mean()).round(3),'const prior',np.sqrt((c**2).sum(1).mean()).round(3))
print('#define SP_B {'+','.join('%.4f'%v for v in Bd.T.ravel())+'}')
print('#define SP_S {'+','.join('%.4f'%v for v in Sd.ravel())+'}')
