import sys,pickle; sys.path.insert(0,'research/single_model/simstruct')
from load import *
R=pickle.load(open('research/single_model/simstruct/t2.pkl','rb'))
Y=[];W=[];S=[];VX=[];ID=[]
for i,r in R.items():
    m=(r['t']>2.0)
    vb=np.einsum('nji,nj->ni',r['Rm'],r['v'])[m][::5]; wz=r['wb'][m][::5][:,2]
    Y.append(vb[:,1]);W.append(wz);S.append(np.linalg.norm(vb[:,:2],axis=1));VX.append(vb[:,0]);ID+= [i]*len(wz)
Y,W,S,VX=map(np.concatenate,(Y,W,S,VX))
k=(Y*(W*S)).sum()/((W*S)**2).sum(); res=Y-k*W*S
print('vb_y = kappa * wz * |v_h| : kappa = %.3f s (heading lag, rad->rad), resid rms %.3f, R2 %.3f'%(k,np.sqrt((res**2).mean()),1-(res**2).sum()/(Y**2).sum()))
# angle form: atan2(vb_y,vb_x) vs wz
ang=np.arctan2(Y,VX); m=S>0.4
kk=(ang[m]*W[m]).sum()/(W[m]**2).sum(); r2=ang[m]-kk*W[m]
print('velocity direction relative to heading: angle = tau*wz, tau=%.3f s, rms resid %.1f deg (raw rms %.1f deg), n=%d'%(kk,np.degrees(np.sqrt((r2**2).mean())),np.degrees(np.sqrt((ang[m]**2).mean())),m.sum()))
for lo,hi in ((0.4,0.8),(0.8,1.5),(1.5,9)):
    mm=m&(S>=lo)&(S<hi); k2=(ang[mm]*W[mm]).sum()/(W[mm]**2).sum(); rr=ang[mm]-k2*W[mm]
    print(f'   speed [{lo},{hi}) tau {k2:.3f}  resid {np.degrees(np.sqrt((rr**2).mean())):.1f} deg  frac resid>60deg {np.mean(np.abs(rr)>1.05):.3f}')
# residual vb_y resid by |wz| bin
for lo,hi in ((0,0.15),(0.15,0.45),(0.45,2)):
    mm=(np.abs(W)>=lo)&(np.abs(W)<hi); print(f'   |wz| [{lo},{hi}): resid vb_y rms {np.sqrt((res[mm]**2).mean()):.3f}  n {mm.sum()}  raw vb_y rms {np.sqrt((Y[mm]**2).mean()):.3f}')
