"""sim.py SRC "DEFS" [--v] : native build of SRC with DEFS, run on cache/*.npz, print mean ATE (RMSE) etc. Fast dev loop (no fuel)."""
import sys,ctypes,subprocess,glob,json,numpy as np,hashlib,os
from concurrent.futures import ProcessPoolExecutor
NAT='/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native'
def build(src,defs):
    h=hashlib.md5((open(src).read()+defs).encode()).hexdigest()[:10];so=f'/dev/shm/e1_{h}.so'
    if not os.path.exists(so):
        subprocess.check_call(['gcc','-O2','-shared','-fPIC','-I'+NAT,*['-D'+d for d in defs.split()],'-o',so,src,'-lm'])
    return so
DBG='--dbg' in sys.argv
DEFS=sys.argv[2] if len(sys.argv)>2 else ''
def run(a):
    so,f=a;L=ctypes.CDLL(so);L.step.argtypes=[ctypes.c_double,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int32,ctypes.c_void_p]
    d=np.load(f);cfg=json.dumps({'width':320,'height':240,'fx':float(d['fx']),'fy':float(d['fx']),'cx':float(d['cx']),'cy':float(d['cy']),'T_cam_imu':[float(x) for x in d['T']]}).encode()
    assert L.init(cfg,len(cfg))==0
    g=d['g'];imu=np.ascontiguousarray(d['imu']);N=len(g);est=np.zeros((N,3));qe=np.zeros((N,4));out=np.zeros(13);rgb=np.zeros((240,320,3),np.uint8)
    ORA='ORACLE' in DEFS
    if ORA:
        T=d['T'].reshape(4,4);Rbc=T[:3,:3].T;Rg=d['Rgt'];Rw0=Rg[0]@Rbc.T  # R_w,b0 ... Rg=R(q)@Rbc -> R(q)=Rg@Rbc.T
        (ctypes.c_float*3).in_dll(L,'ORV')[:]=[999,0,0]
        (ctypes.c_float*3).in_dll(L,'ORG')[:]=list((Rw0.T@np.array([0,0,-9.81])).astype(np.float32))
    for k in range(N):
        if ORA:
            Rb=Rbc@(Rg[0].T@Rg[k])@Rbc.T;(ctypes.c_float*9).in_dll(L,'ORC')[:]=list(Rb.astype(np.float32).ravel())
        rgb[:,:,1]=g[k]
        L.step(float(d['t'][k]),rgb.ctypes.data,imu[k].ctypes.data,10,out.ctypes.data);est[k]=out[:3];qe[k]=out[3:7]
    e=np.linalg.norm(est-d['gt'],axis=1)
    if DBG:
        Rg=d['Rgt'];R0=Rg[0];ang=[]
        for k in (100,300,600,1199):
            x,y,z,w=qe[k];Re=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            Rt=R0.T@Rg[k];ang.append(np.degrees(np.arccos(np.clip((np.trace(Re.T@Rt)-1)/2,-1,1))))
        print(os.path.basename(f),'att err deg@100,300,600,1199',np.round(ang,1),'ate',e.mean(),'err@100,300,600',e[[100,300,600]].round(1))
    return os.path.basename(f),float(np.sqrt((e**2).mean())),float(np.linalg.norm(np.diff(d['gt'],axis=0),axis=1).sum()),float(e[-1])
if __name__=='__main__':
    so=build(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else '');fl=sorted(glob.glob('/data/backups/rganapa/Sebastian/gen3/research/e1/cache/*.npz'))
    with ProcessPoolExecutor(8) as ex: R=list(ex.map(run,[(so,f) for f in fl]))
    a=np.array([r[1] for r in R]);pl=np.array([r[2] for r in R])
    print('ATE mean %.3f med %.3f max %.2f | path mean %.1f | end-err mean %.2f'%(a.mean(),np.median(a),a.max(),pl.mean(),np.mean([r[3] for r in R])))
    if '--v' in sys.argv: [print(r) for r in R]
