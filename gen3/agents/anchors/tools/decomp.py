"""venv python -I tools/decomp.py EVALDIR POOLDIR: per-flight error decomposition: raw ATE, after best yaw about start, after best scale, both"""
import sys,glob,json,numpy as np
sys.path.insert(0,'/data/backups/rganapa/Sebastian/eecs116_projects')
from research.wasm_eval import read_episode,load_estimates
ev,pool=sys.argv[1],sys.argv[2];meta={}
out=[]
for d in sorted(glob.glob(ev+'/*/report/logs/*/estimate.tum')):
    fid=d.split('/')[-5];z=f'{pool}/{fid}.zip'
    try: e=read_episode(z,frames='none')
    except Exception: continue
    est=load_estimates(d,e.frame_times)[:,:3];gt=e.ground_truth_state()[:,:3]
    a=est-gt[0];b=gt-gt[0];raw=np.sqrt(np.mean(np.sum((est-gt)**2,1)))
    # yaw only
    num=np.sum(a[:,0]*b[:,1]-a[:,1]*b[:,0]);den=np.sum(a[:,0]*b[:,0]+a[:,1]*b[:,1]);th=np.arctan2(num,den)
    c,s=np.cos(th),np.sin(th);ay=np.c_[c*a[:,0]-s*a[:,1],s*a[:,0]+c*a[:,1],a[:,2]]
    yaw=np.sqrt(np.mean(np.sum((ay-b)**2,1)))
    k=np.sum(a*b)/max(np.sum(a*a),1e-9);sc=np.sqrt(np.mean(np.sum((k*a-b)**2,1)))
    k2=np.sum(ay*b)/max(np.sum(ay*ay),1e-9);both=np.sqrt(np.mean(np.sum((k2*ay-b)**2,1)))
    hz=np.sqrt(np.mean(np.sum((est-gt)[:,:2]**2,1)));vz=np.sqrt(np.mean((est-gt)[:,2]**2))
    path=np.sum(np.linalg.norm(np.diff(gt,axis=0),axis=1))
    out.append((fid,raw,yaw,sc,both,np.degrees(th),k,hz,vz,path))
A=np.array([o[1:] for o in out])
print('n',len(A),'mean raw %.3f | yaw-fixed %.3f | scale-fixed %.3f | both %.3f | median yaw %.1f deg |abs| %.1f, median scale %.3f (|ln k| %.3f) | horiz %.3f vert %.3f | path %.1f m'%(A[:,0].mean(),A[:,1].mean(),A[:,2].mean(),A[:,3].mean(),np.median(A[:,4]),np.median(abs(A[:,4])),np.median(A[:,5]),np.median(abs(np.log(np.clip(A[:,5],1e-3,None)))),A[:,6].mean(),A[:,7].mean(),A[:,8].mean()))
json.dump(out,open(sys.argv[3] if len(sys.argv)>3 else '/dev/null','w'))
