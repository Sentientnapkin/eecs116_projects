import sys,pickle; sys.path.insert(0,'research/single_model/simstruct')
from load import *
R=pickle.load(open('research/single_model/simstruct/t2.pkl','rb'))
q=lambda x,ps=(50,90,99,100): ' '.join(f'{np.percentile(x,p):.2f}' for p in ps)
st=[r for k,r in R.items() if k.startswith('fast-')]; md=[r for k,r in R.items() if k.startswith('fastmid')]
print(len(st),len(md))
# restrict to flight phase (t>1.2 s) for statics
def cat(rs,key,tmin=1.5):
    return np.concatenate([r[key][r['t']>=tmin] if np.ndim(r[key])>0 and len(r[key])==len(r['t']) else r[key] for r in rs])
A=st+md
print('== thrust-axis vs (a-g) direction error (deg) [flatness: should be ~0]:',q(cat(A,'flat_err')))
ah=np.linalg.norm(cat(A,'a')[:,:2],axis=1); az=cat(A,'a')[:,2]
print('|a_h| m/s2  p50/90/99/max',q(ah),' |a_z|',q(np.abs(az)))
print('|jerk| m/s3',q(np.linalg.norm(cat(A,'jk'),axis=1)))
print('tilt deg',q(cat(A,'tilt')),' yaw rate |rad/s|',q(np.abs(cat(A,'yawrate'))),' |w| body',q(np.linalg.norm(cat(A,'wb'),axis=1)))
print('speed',q(np.linalg.norm(cat(A,'v'),axis=1)),' horiz',q(cat(A,'sh')))
# heading vs velocity direction
sh=cat(A,'sh'); dl=np.abs(cat(A,'delta'))
for lo,hi in ((0.1,0.3),(0.3,0.6),(0.6,1.0),(1.0,1.5),(1.5,2.5),(2.5,9)):
    m=(sh>=lo)&(sh<hi); print(f'  hspeed [{lo},{hi}) n={m.sum():7d} |heading-velocity dir| deg p50/75/90/99: {q(dl[m],(50,75,90,99))}   frac>90deg {np.mean(dl[m]>90):.3f}')
print('overall frac |delta|>90 at hs>0.5: %.3f ; >45: %.3f'%(np.mean(dl[sh>0.5]>90),np.mean(dl[sh>0.5]>45)))
# lag: heading vs velocity direction at lags
def lagstat(rs,lags=(-60,-40,-20,0,20,40,60,100,200)):
    for L in lags:
        dd=[]
        for r in rs:
            n=len(r['t']); ok=(r['t']>1.5)
            hd=np.arctan2(r['v'][:,1],r['v'][:,0]); yaw=r['yaw']
            i=np.arange(n); j=np.clip(i+L,0,n-1)
            dlt=np.abs(np.degrees((hd[i]-yaw[j]+np.pi)%(2*np.pi)-np.pi)); m=ok&(r['sh']>0.5)
            dd.append(dlt[m])
        dd=np.concatenate(dd); print(f'  lag {L*5:+4d} ms: median |vel dir(t) - yaw(t+lag)| {np.median(dd):.1f} deg  mean {dd.mean():.1f}  frac>90 {np.mean(dd>90):.3f}')
print('lag scan (positive lag: yaw LATER than velocity direction)'); lagstat(A)
# body-frame velocity: lateral and backward
vb=np.concatenate([np.einsum('nji,nj->ni',r['Rm'],r['v'])[r['t']>=1.5] for r in A])
print('body vel rms x,y,z',np.sqrt((vb**2).mean(0)).round(3),' frac vb_x<0 (backward) among hs>0.5: %.3f'%np.mean(vb[sh>0.5,0]<0))
# tilt vs acceleration in body frame
ab=np.concatenate([np.einsum('nji,nj->ni',r['Rm'],r['a'])[r['t']>=1.5] for r in A])
print('body-frame world-accel (gravity-free) std x,y,z',ab.std(0).round(2),'   corr(ab_x, vb_x)=%.2f corr(ab_y,vb_y)=%.2f'%(np.corrcoef(ab[:,0],vb[:,0])[0,1],np.corrcoef(ab[:,1],vb[:,1])[0,1]))
