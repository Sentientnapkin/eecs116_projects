"""T5: can the frame-0 IMU window (gyro mean, |f|) predict start velocity / tilt on mid starts?  Truth only for evaluation."""
import sys,pickle; sys.path.insert(0,'research/single_model/simstruct')
from load import *
Rcb=np.array([[0,-1,0],[0,0,-1],[1,0,0]],float)
rows=[]
for d in roster('mid',400,seed=3):
    e=load(d); gt=e.ground_truth; t=gt[:,0]; i0=int(np.searchsorted(t,e.frame_times[0]-1e-9))
    p=gt[i0-6:i0+7,1:4]; Rm=q2R(gt[i0-6:i0+7,4:8]); v=(p[-1]-p[0])/(t[i0+6]-t[i0-6]); R0=Rm[6]
    vb=R0.T@v; w=e.imu_window(0); g=w[:,4:7].mean(0); f=w[:,1:4].mean(0)
    # truth angular velocity body at frame0 (rotvec over +-3 samples)
    wt=rotvec_rel(Rm[3:4],Rm[9:10])[0]/(6*0.005)
    # accel window: mean of truth world accel 
    up_b=R0.T@np.array([0,0,1.])
    rows.append(dict(vb=vb,gyro=g,f=f,wt=wt,up_b=up_b,speed=np.linalg.norm(v),id=d['id']))
pickle.dump(rows,open('research/single_model/simstruct/t5.pkl','wb'))
G=np.array([r['gyro'] for r in rows]); F=np.array([r['f'] for r in rows]); VB=np.array([r['vb'] for r in rows]); UB=np.array([r['up_b'] for r in rows]); sp=np.array([r['speed'] for r in rows])
print('n',len(rows))
print('corr gyro_z vs truth wz: %.3f  (gyro = w + bias + noise/sqrt(10))'%np.corrcoef(G[:,2],[r['wt'][2] for r in rows])[0,1])
def r2(X,y):
    X=np.c_[X,np.ones(len(X))]; b=np.linalg.lstsq(X,y,rcond=None)[0]; return 1-((y-X@b)**2).sum()/((y-y.mean())**2).sum()
feats={'|wz|':np.abs(G[:,2])[:,None],'wz,wy,wx':G,'|w|':np.linalg.norm(G,axis=1)[:,None],'fz':F[:,2:3],'|wz|,fz,|w|':np.c_[np.abs(G[:,2]),F[:,2],np.linalg.norm(G,axis=1)]}
for k,X in feats.items():
    print(f'  R2 speed ~ {k:14s}: {r2(X,sp):.3f}   R2 vb_x: {r2(X,VB[:,0]):.3f}  vb_y: {r2(X,VB[:,1]):.3f}  vb_z: {r2(X,VB[:,2]):.3f}   tilt-x(body up_x): {r2(X,UB[:,0]):.3f} up_y: {r2(X,UB[:,1]):.3f}')
# yaw-rate state: saturated turning fraction
wz=G[:,2]; print('frac |gyro_z|>0.45 (turning at limit):',np.mean(np.abs(wz)>0.45).round(3),' frac |gyro_z|<0.15:',np.mean(np.abs(wz)<0.15).round(3))
for lo,hi in ((0,0.15),(0.15,0.45),(0.45,2)):
    m=(np.abs(wz)>=lo)&(np.abs(wz)<hi); print(f'  |wz| in [{lo},{hi}) n={m.sum()}: speed mean {sp[m].mean():.2f}  vb_x mean {VB[m,0].mean():.2f} |vb_y| mean {np.abs(VB[m,1]).mean():.2f}  tilt deg mean {np.degrees(np.arccos(np.clip(UB[m,2],-1,1))).mean():.1f}')
# sign: turning left (wz>0) -> lateral velocity sign?
m=np.abs(wz)>0.45; print('corr(sign wz * vb_y) in turning:',np.corrcoef(np.sign(wz[m]),VB[m,1])[0,1].round(3),' corr(wz, vb_y) all',np.corrcoef(wz,VB[:,1])[0,1].round(3))
