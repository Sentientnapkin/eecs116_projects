import sys,pickle; sys.path.insert(0,'research/single_model/simstruct')
from load import *
rows=pickle.load(open('research/single_model/simstruct/t3.pkl','rb'))
V=np.array([r['vc'] for r in rows]); U=np.array([r['up_c'] for r in rows]); A=np.array([r['ac'] for r in rows]); sp=np.array([r['speed'] for r in rows]); tl=np.array([r['tilt'] for r in rows]); crop=np.array([r['crop'] for r in rows])
q=lambda x,ps=(10,25,50,75,90,99): ' '.join(f'{np.percentile(x,p):.2f}' for p in ps)
print('n mid flights',len(rows),' crop_start_s min/max/mean',crop.min(),crop.max(),crop.mean().round(1))
print('start speed pct 10/25/50/75/90/99:',q(sp),' mean %.2f'%sp.mean())
print('start tilt deg pct:',q(tl),' mean %.1f'%tl.mean())
print('vc (camera-0 axes x right,y down,z fwd) mean',V.mean(0).round(2),' std',V.std(0).round(2))
print('  corr matrix of vc:\n',np.corrcoef(V.T).round(2))
print('up vector camera: mean',U.mean(0).round(3),' std',U.std(0).round(3),' (level => (0,-1,0)); roll comp ux std %.3f rad, pitch comp uz std %.3f rad'%(U[:,0].std(),U[:,2].std()))
print('corr(ux,vx)=%.2f corr(uz,vz)=%.2f corr(ux,vz)=%.2f corr(uz,vx)=%.2f'%(np.corrcoef(U[:,0],V[:,0])[0,1],np.corrcoef(U[:,2],V[:,2])[0,1],np.corrcoef(U[:,0],V[:,2])[0,1],np.corrcoef(U[:,2],V[:,0])[0,1]))
print('corr(uz, accel_z)=%.2f corr(ux, accel_x)=%.2f  (tilt-accel link)'%(np.corrcoef(U[:,2],A[:,2])[0,1],np.corrcoef(U[:,0],A[:,0])[0,1]))
print('start accel in cam axes std',A.std(0).round(2),' |a_h| ~ ', q(np.hypot(A[:,0],A[:,2])))
# angle between velocity and optical axis
ang=np.degrees(np.arccos(np.clip(V[:,2]/np.maximum(np.linalg.norm(V,axis=1),1e-6),-1,1)))
m=sp>0.3; print('angle(optical axis, velocity) deg, speed>0.3 (n=%d): median %.0f, frac>90: %.2f, frac<45 %.2f'%(m.sum(),np.median(ang[m]),np.mean(ang[m]>90),np.mean(ang[m]<45)))
hang=np.degrees(np.abs(np.arctan2(V[:,0],V[:,2])))
print('horizontal-plane (x,z) heading-velocity angle, hs>0.3: median %.0f frac>90 %.2f'%(np.median(hang[np.hypot(V[:,0],V[:,2])>0.3]),np.mean(hang[np.hypot(V[:,0],V[:,2])>0.3]>90)))
# how much of speed variance is explained by crop time
print('corr(speed, crop_s)=%.2f ; speed by crop bin:'%np.corrcoef(sp,crop)[0,1],[ (lo,round(sp[(crop>=lo)&(crop<lo+10)].mean(),2)) for lo in (0,10,20,30)])
# best constant-mean Gaussian prior vs current prior (0.9 fwd, sigma .5,.35,.6): log-lik / mean error
for name,mu,sd in (('current gate prior (0,0,.9; .5,.35,.6)',[0,0,.9],[.5,.35,.6]),('fitted mean/std',V.mean(0),V.std(0))):
    mu=np.array(mu);sd=np.array(sd); z=(V-mu)/sd; print(name,' mean z^2 per axis',(z**2).mean(0).round(2),' mean |v-mu| %.2f'%np.linalg.norm(V-mu,axis=1).mean())
# scaling: speed distribution lognormal? compare with half-normal sigma
print('3D speed: mean %.2f rms %.2f; horizontal part:'%(sp.mean(),np.sqrt((sp**2).mean())))
