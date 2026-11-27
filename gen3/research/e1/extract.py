"""extract.py POOLDIR OUTDIR [step] : per-flight npz: g (N,240,320) uint8 G of 2x2-area-averaged frames, imu (N,10,7) ABI order, gt p (N,3) in cam0 frame, t, cfg."""
import sys,zipfile,json,io,numpy as np,os
from pathlib import Path
from PIL import Image
from concurrent.futures import ProcessPoolExecutor
def one(a):
    zf,out=a
    if Path(out).exists(): return
    z=zipfile.ZipFile(zf);n=z.namelist();r=n[0].split('/')[0]
    ep=json.loads(z.read(r+'/episode.json'))
    rows=[l.split(',') for l in z.read(r+'/mav0/cam0/data.csv').decode().splitlines()[1:]]
    ts=np.array([int(x[0]) for x in rows]);fn=[x[1].strip() for x in rows]
    G=np.zeros((len(ts),240,320),np.uint8)
    for i,f in enumerate(fn):
        im=np.asarray(Image.open(io.BytesIO(z.read(r+'/mav0/cam0/data/'+f))).convert('RGB'),dtype=np.uint16)
        g=im[:,:,1];G[i]=((g[0::2,0::2]+g[0::2,1::2]+g[1::2,0::2]+g[1::2,1::2]+2)>>2)
    im=np.loadtxt(io.StringIO(z.read(r+'/mav0/imu0/data.csv').decode()),delimiter=',',skiprows=1)
    gt=np.loadtxt(io.StringIO(z.read(r+'/mav0/state_groundtruth_estimate0/data.csv').decode()),delimiter=',',skiprows=1)
    # imu rows per frame: t_prev < t <= t_frame
    I=np.zeros((len(ts),10,7))
    for k,t in enumerate(ts):
        sel=np.where((im[:,0]<=t)&(im[:,0]>t-50e6))[0][-10:]
        row=im[sel]; I[k,:len(row),0]=row[:,0]*1e-9;I[k,:len(row),1:4]=row[:,4:7];I[k,:len(row),4:7]=row[:,1:4]
    gi=np.searchsorted(gt[:,0],ts);gi=np.clip(gi,0,len(gt)-1)
    P=gt[gi,1:4]
    q=gt[gi,4:8] # w x y z
    def R(q):
        w,x,y,z=q;return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    c=ep['config'];cam=c['camera'];Rbc=np.array(c['imu']['T_cam_imu']).reshape(4,4)[:3,:3].T
    R0=R(q[0])@Rbc;Pc=(P-P[0])@R0   # GT file is the IMU/body frame; camera = body*Rbc
    np.savez(out,g=G,imu=I,gt=Pc,t=ts*1e-9,fx=cam['fx']/2,cx=(cam['cx']+.5)/2-.5,cy=(cam['cy']+.5)/2-.5,T=np.array(c['imu']['T_cam_imu']),Rgt=np.array([R(x)@Rbc for x in q]))
if __name__=='__main__':
    P=sorted(Path(sys.argv[1]).glob('*.zip'));O=Path(sys.argv[2]);O.mkdir(exist_ok=True,parents=True);st=int(sys.argv[3]) if len(sys.argv)>3 else 1
    with ProcessPoolExecutor(6) as ex: list(ex.map(one,[(str(p),str(O/(p.stem+'.npz'))) for p in P[::st]]))
