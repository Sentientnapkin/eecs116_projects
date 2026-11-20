"""T1: IMU model check from truth. measured = f_true + b + n.  accel x,y: f_true=0 (thrust-only, no drag). gyro: w_true + b + n."""
import sys; sys.path.insert(0,'research/single_model/simstruct')
from load import *
res=[]
for kind in ('static','mid'):
    for d in roster(kind,24,seed=1):
        e=load(d); gt=e.ground_truth; imu=e.imu
        # align: imu row i stamped t_i; gt rows at t. find gt idx for each imu stamp
        ti=imu[:,0]; tg=gt[:,0]
        idx=np.searchsorted(tg,ti-1e-9)  # gt state at imu stamp (state after the step)
        idx=np.clip(idx,1,len(tg)-1)
        Rm=q2R(gt[:,4:8])
        # truth angular velocity (body) over step ending at stamp: log(R_{i-1}^-1 R_i)/dt
        wb=rotvec_rel(Rm[idx-1],Rm[idx])/0.005
        # truth specific force: a = (v_i - v_{i-1})/dt - g ; v by central diff of position around step: use p second-difference
        p=gt[:,1:4]
        v=(p[1:]-p[:-1])/0.005  # v at midpoints
        # acceleration over step ending idx: (v[idx]-v[idx-1])/dt  (v[k]=between k,k+1) approx
        a=np.zeros((len(idx),3)); ok=(idx>=2)&(idx<len(tg)-1)
        a[ok]=(v[idx[ok]]-v[idx[ok]-2])/0.01
        a[~ok]=np.nan
        f_world=a+np.array([0,0,9.81])
        fb=np.einsum('nji,nj->ni',Rm[idx],f_world)
        gm=imu[:,4:7]-wb; am=imu[:,1:4]
        # residual in x,y: measured accel minus truth force
        rx=am[:,:2]-fb[:,:2]; rz=am[:,2]-fb[:,2]
        m=~np.isnan(fb).any(1)&(ti>1.2)
        # noise std from first-difference
        def nstd(x): x=x[m]; return np.nanstd(np.diff(x,axis=0),axis=0)/np.sqrt(2)
        bg0=gm[(ti>0.05)&(ti<1.0)].mean(0); bg1=gm[ti>ti[-1]-1.0].mean(0)
        ba0=am[(ti>0.05)&(ti<1.0),:2].mean(0); ba1=am[ti>ti[-1]-1.0,:2].mean(0)
        res.append(dict(kind=kind,id=d['id'],f_xy_rms=np.sqrt(np.nanmean(fb[m,:2]**2)),f_z_mean=np.nanmean(fb[m,2]),
            nz_g=nstd(gm), nz_a=nstd(am), resz_std=np.nanstd(rz[m]), bg0=bg0, bg1=bg1, ba0=ba0, ba1=ba1,
            rx_std=np.nanstd(rx[m],axis=0), fbxy_std=np.nanstd(fb[m,:2],axis=0)))
import pickle; pickle.dump(res,open('research/single_model/simstruct/t1.pkl','wb'))
A=lambda k:np.array([r[k] for r in res])
print('n flights',len(res))
print('truth lateral force body x,y rms (m/s2) [should be ~0 if thrust-only]: median %.4f  max %.4f'%(np.median(A('f_xy_rms')),A('f_xy_rms').max()))
print('per-sample noise std gyro xyz median',np.median(A('nz_g'),0).round(4),' accel xyz',np.median(A('nz_a'),0).round(4))
print('  (nominal gyro .07, accel .28; first-difference estimator includes signal diffs)')
bg=np.vstack([A('bg0')]); print('gyro bias est first 1 s: max abs per axis',np.abs(bg).max(0).round(4),'std',bg.std(0).round(4),'(uniform +-.02 => std .0115)')
ba=A('ba0'); print('accel xy bias est first 1 s: max abs',np.abs(ba).max(0).round(3),'std',ba.std(0).round(3),'(uniform +-.2 => std .115)')
dg=(A('bg1')-A('bg0')); da=(A('ba1')-A('ba0'))
print('gyro bias drift over ~59 s: std',dg.std(0).round(4),' expected sqrt(59)*.0006 = %.4f (+meas noise %.4f)'%(0.0006*59**.5, 0.07/200**.5*2**.5))
print('accel xy bias drift: std',da.std(0).round(4),' expected %.4f (+meas noise %.4f)'%(0.001*59**.5, .28/200**.5*2**.5))
