"""Motion sweep: fly settings, compute the probe's statistics from IMU/GT (no files written). python sweep.py ROSTER OUT W N"""
import sys,json,time,traceback,numpy as np
R='/data/backups/rganapa/Sebastian/';sys.path[:0]=[R+'eecs116_projects/research',R+'gen3']
import viobench.tools.datasets.generate.simulation as S
from native_campaign import apply_task_overrides
from g3 import ref
def stats(ep):
    imu=ep.imu;ft=ep.frame_times;n=min(1130,len(ft));m=imu[:,0]<=ft[n-1]+1e-9;g=imu[m,4:7];a=imu[m,1:4]
    k=(len(a)//10)*10;fa=a[:k].reshape(-1,10,3).mean(1);jerk=np.sqrt((np.linalg.norm(np.diff(fa,axis=0),axis=1)/.05)**2).mean() if 0 else float(np.sqrt(np.mean(np.sum((np.diff(fa,axis=0)/.05)**2,1))))
    gt=ep.ground_truth;gt=gt[gt[:,0]>=ft[0]-1e-9];p=gt[:,1:4];d=np.linalg.norm(np.diff(p,axis=0),axis=1).sum();dur=gt[-1,0]-gt[0,0]
    return dict(gyro=float(np.sqrt((g**2).sum(1).mean())),yaw=float(np.sqrt((g[:,2]**2).mean())),rp=float(np.sqrt((g[:,:2]**2).sum(1).mean())),jerk=jerk,speed=float(d/dur),path60=float(d/dur*60),rmsd=float(np.sqrt(((p-p[0])**2).sum(1).mean())))
ro,out,w,n=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
for f in json.load(open(ro))['flights'][w::n]:
    t=time.time()
    try:
        apply_task_overrides(f['task_overrides'])
        sim=S.SimConfig(instances=1,duration_seconds=f['seconds'],hold_seconds=.2,waypoints=48,fov=105.,fov_range=30.)
        ep,=S.simulate(sim,ref(f),1,seed=f['seed'],name='sw',log=lambda m:None);r={**f,**stats(ep),'ok':1}
    except Exception as e: r={**f,'ok':0,'err':repr(e)[:200]};traceback.print_exc()
    r['s']=round(time.time()-t);open(out,'a').write(json.dumps(r)+'\n')
