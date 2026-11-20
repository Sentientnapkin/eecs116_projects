"""T3: start-state distribution of the crop (our construction, native_campaign.crop_episode) from truth; frame-0 state in camera-0 axes.
 body FLU: x fwd, y left, z up.  camera: x right = -body y, y down = -body z, z fwd = body x."""
import sys,pickle,time; sys.path.insert(0,'research/single_model/simstruct')
from load import *
Rcb=np.array([[0,-1,0],[0,0,-1],[1,0,0]],float)   # body->camera: v_c = Rcb v_b
rows=[]; t0=time.time()
ds=roster('mid',400,seed=3)
for d in ds:
    e=load(d); gt=e.ground_truth; t=gt[:,0]; i0=int(np.searchsorted(t,e.frame_times[0]-1e-9))
    s=slice(max(i0-6,0),i0+7)
    p=gt[s,1:4]; Rm=q2R(gt[s,4:8]); j=i0-s.start
    v=(p[-1]-p[0])/(t[s][-1]-t[s][0])           # world velocity, ~65 ms central
    # smoother over +-30 ms centred: use indices j-6..j+6 if available
    R0=Rm[j]; vb=R0.T@v; vc=Rcb@vb
    up_b=R0.T@np.array([0,0,1.]); up_c=Rcb@up_b
    tilt=np.degrees(np.arccos(np.clip(up_b[2],-1,1)))
    w=rotvec_rel(Rm[max(j-3,0):j+1],Rm[max(j-3,0)+1:j+2])/0.005 if False else None
    a=(gt[i0+10,1:4]-2*gt[i0,1:4]+gt[max(i0-10,0),1:4])/(0.05**2)
    rows.append(dict(id=d['id'],crop=d['crop_start_s'],vc=vc,speed=np.linalg.norm(v),tilt=tilt,up_c=up_c,ac=Rcb@(R0.T@a),setting=d['setting'],vz=v[2]))
print('n',len(rows),'%.0fs'%(time.time()-t0))
pickle.dump(rows,open('research/single_model/simstruct/t3.pkl','wb'))
