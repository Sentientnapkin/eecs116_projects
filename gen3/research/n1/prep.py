import sys,zipfile,io,numpy as np,glob,os
from concurrent.futures import ProcessPoolExecutor
def qR(q):
    w,x,y,z=q.T
    R=np.empty((len(w),3,3))
    R[:,0,0]=1-2*(y*y+z*z);R[:,0,1]=2*(x*y-z*w);R[:,0,2]=2*(x*z+y*w)
    R[:,1,0]=2*(x*y+z*w);R[:,1,1]=1-2*(x*x+z*z);R[:,1,2]=2*(y*z-x*w)
    R[:,2,0]=2*(x*z-y*w);R[:,2,1]=2*(y*z+x*w);R[:,2,2]=1-2*(x*x+y*y)
    return R
def one(a):
    f,o=a
    if os.path.exists(o):return
    z=zipfile.ZipFile(f);r=z.namelist()[0].split('/')[0]
    im=np.loadtxt(io.StringIO(z.read(r+'/mav0/imu0/data.csv').decode()),delimiter=',',skiprows=1)
    gt=np.loadtxt(io.StringIO(z.read(r+'/mav0/state_groundtruth_estimate0/data.csv').decode()),delimiter=',',skiprows=1)
    t=im[:,0]*1e-9;tg=gt[:,0]*1e-9
    ok=(t>=tg[0])&(t<=tg[-1]);im=im[ok];t=t[ok]
    p=np.stack([np.interp(t,tg,gt[:,1+i]) for i in range(3)],1)
    # velocity: central diff on 200Hz GT, smoothed 5 samples
    dt=np.median(np.diff(tg));vg=np.gradient(gt[:,1:4],dt,axis=0)
    k=np.ones(5)/5;vg=np.stack([np.convolve(vg[:,i],k,'same') for i in range(3)],1)
    v=np.stack([np.interp(t,tg,vg[:,i]) for i in range(3)],1)
    Rg=qR(gt[:,4:8]);
    # nearest GT rotation per imu sample
    idx=np.clip(np.searchsorted(tg,t),0,len(tg)-1);R=Rg[idx]
    # true gyro from GT
    dR=np.einsum('nji,njk->nik',Rg[:-1],Rg[1:]) # R_k^T R_{k+1}
    ang=np.arccos(np.clip((np.trace(dR,axis1=1,axis2=2)-1)/2,-1,1))
    sk=np.stack([dR[:,2,1]-dR[:,1,2],dR[:,0,2]-dR[:,2,0],dR[:,1,0]-dR[:,0,1]],1)/2
    s=np.sinc(ang/np.pi)[:,None]; wg=sk/np.maximum(s,1e-9)/dt
    wgi=np.stack([np.interp(t,tg[:-1],wg[:,i]) for i in range(3)],1)
    np.savez(o,t=t,gyro=im[:,1:4],acc=im[:,4:7],p=p,v=v,R=R,wgt=wgi)
if __name__=='__main__':
    fl=sorted(glob.glob('/data/backups/rganapa/Sebastian/gen3/pools/v3val/*.zip'))
    st=int(sys.argv[1]);fl=fl[::st]
    with ProcessPoolExecutor(8) as ex: list(ex.map(one,[(f,'cache/'+os.path.basename(f)[:-4]+'.npz') for f in fl]))
