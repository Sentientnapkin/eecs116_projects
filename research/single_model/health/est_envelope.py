"""How often does the (baseline) ESTIMATE violate the true-flight envelope? vs ATE. usage: est_envelope.py <run name>"""
import sys; sys.path.insert(0,'.')
from pathlib import Path
import numpy as np
from research.guard_fusion import traj as T
from research.single_model.run_variant import tags, fold, slice_of, ate_rows
name=sys.argv[1]
folder=next((Path('research/results/single_model')/name/'eval').glob(name+'-*'))
ate=ate_rows(folder/'scores.json'); tg=tags()
def q2m(q):
    x,y,z,w=q.T
    return np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],1).reshape(-1,3,3)
Rbc=np.array([[0,0,1],[-1,0,0],[0,-1,0]],float)
out=[]
for ep in sorted(ate):
    if slice_of(fold(tg[ep]))!='search': continue
    e=T.read_episode(Path(T.DEFAULT_RAW)/f'{ep}.zip',frames='none')
    t=np.asarray(e.frame_times); cw=np.asarray(e.camera_poses_world()); Rwc0=q2m(cw[:1,3:7])[0]
    paths=sorted((folder/ep/'report/logs').glob('*/estimate.tum')); est=T.fill_missing_states(T.load_estimates(paths[0],t))
    pw=(Rwc0@est[:,:3].T).T; Rk=q2m(est[:,3:7]); Rwb=np.einsum('ij,njk->nik',Rwc0,Rk)@Rbc.T
    vw=np.einsum('nij,nj->ni',np.einsum('ij,njk->nik',Rwc0,Rk),est[:,7:10])
    sp=np.linalg.norm(est[:,7:10],axis=1); tilt=np.degrees(np.arccos(np.clip(Rwb[:,2,2],-1,1)))
    k=np.ones(5)/5
    z=pw[:,2]-pw[0,2]
    out.append((ep,tg[ep]['start'],ate[ep],sp.max(),np.abs(vw[:,2]).max(),tilt.max(),np.abs(z).max(),(sp>3.0).sum(),(sp>2.5).sum(),(np.abs(vw[:,2])>1.5).sum(),(tilt>40).sum()))
A=np.array([o[2:] for o in out],float); bad=A[:,0]>5
print('estimate quantities: bad(>5m) n=%d vs ok n=%d'%(bad.sum(),(~bad).sum()))
for i,nm in enumerate(['ate','max speed','max |vz|','max tilt','max|z-z0|','frames sp>3','frames sp>2.5','frames |vz|>1.5','frames tilt>40']):
    print(f'{nm:16s} bad: med {np.median(A[bad,i]):7.2f} max {A[bad,i].max():7.2f} | ok: med {np.median(A[~bad,i]):6.2f} p95 {np.percentile(A[~bad,i],95):6.2f} max {A[~bad,i].max():6.2f}')
for thr in [(1,3.0),(1,3.5),(1,4.0),(2,1.5),(2,2.0),(4,2.5),(4,3.0)]:
    f=A[:,thr[0]+0]>thr[1]
    print('col',thr, 'flights above:',f.sum(),'of which bad',(f&bad).sum())
