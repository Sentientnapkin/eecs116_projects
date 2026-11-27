"""i5 prototype shard builder (CPU): per flight -> one npz with 160x120 gray frames, raw IMU, GT 200Hz pose/vel, per-frame IMU preintegration
(GT-free, raw IMU, bias=0), KLT tracks (GFTT+LK, 160x120), metadata. python shard.py OUTDIR ZIP... ; prints timing JSON line per flight."""
import sys, os, io, json, time, zipfile, numpy as np, cv2
cv2.setNumThreads(1)
def skew(v): return np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]])
def expm(w):
    th=np.linalg.norm(w)
    if th<1e-9: return np.eye(3)+skew(w)
    K=skew(w/th); return np.eye(3)+np.sin(th)*K+(1-np.cos(th))*K@K
def preint(imu_t, gyro, acc, t0, t1):
    m=(imu_t>=t0-1e-9)&(imu_t<t1-1e-9); R=np.eye(3); v=np.zeros(3); p=np.zeros(3); dt=0.005
    for g,a in zip(gyro[m],acc[m]):
        p+=v*dt+0.5*R@a*dt*dt; v+=R@a*dt; R=R@expm(g*dt)
    return np.concatenate([R[[2,0,1],[1,2,0]]-R[[1,2,0],[2,0,1]], v, p, [m.sum()*dt]]).astype(np.float32)  # 3 so(3)-ish, v, p, T
def run(zp, od):
    t00=time.time(); z=zipfile.ZipFile(zp); r=z.namelist()[0].split('/')[0]
    rd=lambda n:np.loadtxt(io.StringIO(z.read(f'{r}/mav0/{n}/data.csv').decode()),delimiter=',',comments='#')
    gt=rd('state_groundtruth_estimate0'); imu=rd('imu0'); ep=json.loads(z.read(f'{r}/episode.json')); t1=time.time()
    c=np.loadtxt(io.StringIO(z.read(f'{r}/mav0/cam0/data.csv').decode()),delimiter=',',comments='#',dtype=str); ft=c[:,0].astype(np.int64)*1e-9
    fr=[]
    for fn in c[:,1]:
        im=cv2.imdecode(np.frombuffer(z.read(f'{r}/mav0/cam0/data/{fn}'),np.uint8),cv2.IMREAD_GRAYSCALE); fr.append(cv2.resize(im,(160,120),interpolation=cv2.INTER_AREA))
    fr=np.stack(fr); t2=time.time()
    it=imu[:,0]*1e-9; pre=np.stack([preint(it,imu[:,1:4],imu[:,4:7],ft[i],ft[i+1]) for i in range(len(ft)-1)]); t3=time.time()
    # KLT tracks: per frame pairs, forward LK on GFTT corners, 80 max, store as (frame, id) x y with simple re-detection
    pts=np.zeros((0,1,2),np.float32); ids=np.zeros(0,int); nid=0; rows=[]
    for i in range(len(fr)):
        if i>0 and len(pts):
            q,s,_=cv2.calcOpticalFlowPyrLK(fr[i-1],fr[i],pts,None,winSize=(15,15),maxLevel=2); ok=s[:,0]==1; pts=q[ok]; ids=ids[ok]
        if len(pts)<60:
            mk=np.full(fr[i].shape,255,np.uint8)
            for x,y in pts[:,0]: cv2.circle(mk,(int(x),int(y)),6,0,-1)
            n=cv2.goodFeaturesToTrack(fr[i],80-len(pts),0.01,6,mask=mk)
            if n is not None: pts=np.concatenate([pts,n.astype(np.float32)]); ids=np.concatenate([ids,np.arange(nid,nid+len(n))]); nid+=len(n)
        for k,(x,y) in zip(ids,pts[:,0]): rows.append((i,k,x,y))
    tr=np.array(rows,np.float32); t4=time.time()
    gtv=np.zeros((len(gt),3)); gtv[1:-1]=(gt[2:,1:4]-gt[:-2,1:4])/0.01
    f=f'{od}/{ep["name"]}.npz'
    np.savez_compressed(f,frames=fr,imu=imu.astype(np.float32),gt=np.concatenate([gt[:,1:8],gtv],1).astype(np.float32),preint=pre,tracks=tr,meta=json.dumps(ep['meta']),cfg=json.dumps(ep['config']))
    t5=time.time(); print(json.dumps(dict(id=ep['name'],read=t1-t00,frames=t2-t1,preint=t3-t2,klt=t4-t3,save=t5-t4,total=t5-t00,bytes=os.path.getsize(f),ntrk=int(nid),rawframes_MB=fr.nbytes/1e6)),flush=True)
if __name__=='__main__':
    os.makedirs(sys.argv[1],exist_ok=True)
    for zp in sys.argv[2:]: run(zp,sys.argv[1])
