"""Flight envelope of the SEARCH slice (folds 0-2) from ground truth. World frame z up (camera_poses_world)."""
import sys, json; sys.path.insert(0,'.')
from pathlib import Path
import numpy as np
from research.guard_fusion import traj as T
from research.single_model.run_variant import tags, fold, slice_of

def q2m(q):
    x,y,z,w=q.T
    return np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],1).reshape(-1,3,3)
tg=tags(); eps=sorted(e for e in tg if slice_of(fold(tg[e]))=='search')
Rcb=np.array([[0,0,1],[-1,0,0],[0,-1,0]],float).T  # T_body_camera rotation = R_bc ; camera->body? check below
rows={}
for ep in eps:
    e=T.read_episode(Path(T.DEFAULT_RAW)/f'{ep}.zip',frames='none')
    cw=np.asarray(e.camera_poses_world()); t=np.asarray(e.frame_times)
    Rwc=q2m(cw[:,3:7])
    Tbc=np.asarray(e.T_body_camera)[:3,:3] if not callable(e.T_body_camera) else np.asarray(e.T_body_camera())[:3,:3]
    Rwb=Rwc@Tbc.T            # R_wc * R_cb ; R_cb = R_bc^T
    p=cw[:,:3]
    v=np.gradient(p,t,axis=0)
    # smooth over 0.2 s
    k=np.ones(5)/5; vs=np.stack([np.convolve(v[:,i],k,'same') for i in range(3)],1)
    zb=Rwb[:,:,2]; tilt=np.degrees(np.arccos(np.clip(zb[:,2],-1,1)))
    vb=np.einsum('nji,nj->ni',Rwb,vs)   # body frame
    sp=np.linalg.norm(vs,axis=1)
    rows[ep]=dict(start=tg[ep]['start'],t=t,z=p[:,2]-p[0,2],vz=vs[:,2],sp=sp,hsp=np.linalg.norm(vs[:,:2],axis=1),tilt=tilt,vb=vb,
                  w=np.asarray(e.ground_truth_state())[:,10:13], vtruth=np.asarray(e.ground_truth_state())[:,7:10],p0=p[0])
    rows[ep]['step']=np.linalg.norm(np.diff(p,axis=0),axis=1)
import pickle; pickle.dump(rows,open('research/single_model/health/envelope.pkl','wb'))
print(len(eps))
def q(x,ps=(50,90,95,99,99.9,100)): return ' '.join(f'{np.percentile(x,p):.2f}' for p in ps)
for grp in ('all','static','mid'):
    R=[r for r in rows.values() if grp=='all' or r['start']==grp]
    cat=lambda k:np.concatenate([r[k] for r in R])
    print('==',grp,len(R),'flights  [pct 50/90/95/99/99.9/max]')
    print('speed',q(cat('sp'))); print('|vz|',q(np.abs(cat('vz')))); print('hsp',q(cat('hsp')))
    print('tilt deg',q(cat('tilt'))); print('|z-z0|',q(np.abs(cat('z'))))
    vb=np.concatenate([r['vb'] for r in R]); print('|v_b lateral y|',q(np.abs(vb[:,1])),' |vb_x|',q(np.abs(vb[:,0])))
    print('|w| rad/s',q(np.linalg.norm(cat('w'),axis=0) if False else np.linalg.norm(np.concatenate([r['w'] for r in R]),axis=1)))
    # per-flight z range
    print('per-flight max|z-z0|',q([np.abs(r['z']).max() for r in R],(50,90,100)),' std z',q([r['z'].std() for r in R],(50,90,100)))
    print('per-flight max speed',q([r['sp'].max() for r in R],(50,90,100)),' mean speed',np.mean([r['sp'].mean() for r in R]).round(2))
    print('mean|vz|',np.mean(np.abs(cat('vz'))).round(3),'rms vz',np.sqrt(np.mean(cat('vz')**2)).round(3),'rms hsp',np.sqrt(np.mean(cat('hsp')**2)).round(3),'rms vb_y',np.sqrt(np.mean(vb[:,1]**2)).round(3),'rms vb_x',np.sqrt(np.mean(vb[:,0]**2)).round(3),'rms vb_z',np.sqrt(np.mean(vb[:,2]**2)).round(3))
    print('max frame step m',q(cat('step')) )
# lateral ratio when moving
vb=np.concatenate([r['vb'] for r in rows.values()]); m=np.hypot(vb[:,0],vb[:,1])>0.3
slip=np.degrees(np.abs(np.arctan2(vb[m,1],vb[m,0]))); print('slip deg when hsp>0.3 body',len(slip),q(slip,(50,75,90,99)))
# truth-v consistency
r=rows[eps[0]]; print('vtruth norm vs finite diff', np.median(np.linalg.norm(r['vtruth'],axis=1)), np.median(r['sp']))
