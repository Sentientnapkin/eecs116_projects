import json, numpy as np
E='research/single_model/edge/'
s=json.load(open(E+'sig.json')); a=json.load(open(E+'audit.json')); f=json.load(open(E+'flightstats.json'))
C=['base','f0','G','T','M']
eps=[e for e in s if all(c in s[e] for c in C)]
A={c:np.array([s[e][c]['ate_rmse'] for e in eps]) for c in C}
F=lambda k: np.array([f[e][k] if f[e][k] is not None else np.nan for e in eps],float)
Au=lambda k: np.array([a[e][k] for e in eps],float)
mid=np.array([a[e]['start']=='mid' for e in eps]); v0=F('v0'); ang=F('ang0')
cls={}
cls['static']=~mid
cls['mid v0<0.3']=mid&(v0<0.3); cls['mid v0 0.3-0.6']=mid&(v0>=0.3)&(v0<0.6); cls['mid v0 0.6-1.2']=mid&(v0>=0.6)&(v0<1.2); cls['mid v0 1.2-1.8']=mid&(v0>=1.2)&(v0<1.8); cls['mid v0>=1.8 (fast)']=mid&(v0>=1.8)
mv=mid&(v0>=0.3)
cls['mid moving, axis<45deg']=mv&(ang<45); cls['mid moving, 45-90']=mv&(ang>=45)&(ang<90); cls['mid moving, 90-135 (lateral/back)']=mv&(ang>=90)&(ang<135); cls['mid moving, >=135 (reverse)']=mv&(ang>=135)
cls['yaw rate max<20 deg/s']=F('yawrate_max')<20; cls['yaw rate max 20-35']=(F('yawrate_max')>=20)&(F('yawrate_max')<35); cls['yaw rate max>=35 (sat.)']=F('yawrate_max')>=35
cls['tilt0 >=12 deg']=F('tilt0')>=12; cls['tilt0 <12']=F('tilt0')<12
cls['tilt_max >=35']=F('tilt_max')>=35
cls['vertical share >=0.35']=F('vz_share')>=0.35
cls['speed_max >=6 m/s']=F('speed_max')>=6; cls['speed_max <4']=F('speed_max')<4
cls['travel >=65 m']=Au('travel')>=65; cls['travel <40 m']=Au('travel')<40
cls['dark_fraction>0.2']=Au('dark')>0.2; cls['flat_fraction>0.2']=Au('flat')>0.2
cls['hover_frac>=0.15']=Au('hover')>=0.15
cls['setting K (3-4.5 m/s cruise)']=np.array([a[e]['cruise'][0]==3.0 for e in eps]); cls['setting K2 (4-6)']=np.array([a[e]['cruise'][0]==4.0 for e in eps])
cls['accel rms top quartile']=F('acc_rms')>=np.nanpercentile(F('acc_rms'),75)
cls['all']=np.ones(len(eps),bool)
L=['| class | n | base mean | f0 | G | T | M | G >3 | G >5 | base >5 | T >5 | G-worse-than-base>1.5 |','|--|--|--|--|--|--|--|--|--|--|--|--|']
for k,m in cls.items():
    if m.sum()==0: continue
    L.append('| %s | %d | %.2f | %.2f | %.2f | %.2f | %.2f | %d (%.0f%%) | %d (%.0f%%) | %d | %d | %d |'%(k,m.sum(),*[A[c][m].mean() for c in C],(A['G'][m]>3).sum(),100*(A['G'][m]>3).mean(),(A['G'][m]>5).sum(),100*(A['G'][m]>5).mean(),(A['base'][m]>5).sum(),(A['T'][m]>5).sum(),((A['G']-A['base'])[m]>1.5).sum()))
print('\n'.join(L))
# percentiles of features for pool (for config ranges)
for k in ('v0','yawrate_max','tilt0','tilt_max','speed_max','acc_rms','vz_share'):
    x=F(k); print(k,np.round(np.nanpercentile(x[mid] if k=='v0' else x,[0,10,50,90,100]),2))
# scale/rot signature among G>3
print('\nG >3 m flights (non-fold4 pool): mechanism table  sig = scale<0.75')
for i in np.argsort(-A['G']):
    if A['G'][i]<3: break
    e=eps[i]; g=s[e]['G']; print('%-36s %-5s G %.2f base %.2f T %.2f rot %.2f vel %.2f sc %.2f v0 %.2f ang %s yaw %.0f tilt0 %.0f flat %.2f dark %.2f'%(e,'mid' if mid[i] else 'stat',A['G'][i],A['base'][i],A['T'][i],g['rotation_rmse'],g['velocity_rmse'],g['sim3_scale'],v0[i],'%.0f'%ang[i] if ang[i]==ang[i] else '-',F('yawrate_max')[i],F('tilt0')[i],a[e]['flat'],a[e]['dark']))
