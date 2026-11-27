"""sim.py SRC "DEFS" [--v] : native build of SRC with DEFS, run on cache/*.npz, print mean ATE (RMSE) etc. Fast dev loop (no fuel)."""
import sys,ctypes,subprocess,glob,json,numpy as np,hashlib,os
from concurrent.futures import ProcessPoolExecutor
NAT='/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native'
def build(src,defs):
    h=hashlib.md5((open(src).read()+defs).encode()).hexdigest()[:10];so=f'/dev/shm/n3_{h}.so'
    if not os.path.exists(so):
        subprocess.check_call(['gcc','-O2','-shared','-fPIC','-Isrc','-I'+NAT,*['-D'+d for d in defs.split()],'-o',so,src,'-lm'])
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
    bgl=np.zeros((N,3));HASB=True
    T_=d['T'].reshape(4,4);Rbc_=T_[:3,:3].T;pg=d['gt'];vg=np.gradient(pg,0.05,axis=0)
    Rr=np.einsum('ji,njk->nik',d['Rgt'][0],d['Rgt']);vb=np.einsum('ij,nkj,nk->ni',Rbc_,Rr,vg)
    (ctypes.c_double).in_dll(L,'stub_noise').value=float(os.environ.get('STUBN','0.44'))
    Rg=d['Rgt'];T=d['T'].reshape(4,4);Rbc=T[:3,:3].T
    from math import acos
    wc=np.zeros((N,3))
    for k in range(1,N):
        M=Rg[k-1].T@Rg[k];a=np.array([M[2,1]-M[1,2],M[0,2]-M[2,0],M[1,0]-M[0,1]])/2;s_=np.linalg.norm(a);th=np.arctan2(s_,(np.trace(M)-1)/2);wc[k]=a/max(s_,1e-12)*th/0.05
    wb=wc@Rbc.T;gy=d['imu'][:,:,4:7].mean(1);bt=gy-wb;btw=np.array([bt[max(1,k-100):k+100].mean(0) for k in range(N)])
    for k in range(N):
        if ORA:
            Rb=Rbc@(Rg[0].T@Rg[k])@Rbc.T;(ctypes.c_float*9).in_dll(L,'ORC')[:]=list(Rb.astype(np.float32).ravel())
        try:(ctypes.c_double*3).in_dll(L,'dbg_bt')[:]=list(btw[k])
        except Exception:pass
        (ctypes.c_double*3).in_dll(L,'stub_v')[:]=list(vb[k])
        rgb[:,:,:]=g[k][:,:,None] if g[k].ndim==2 else g[k]
        L.step(float(d['t'][k]),rgb.ctypes.data,imu[k].ctypes.data,10,out.ctypes.data);est[k]=out[:3];qe[k]=out[3:7]
        try: bgl[k]=(ctypes.c_double*3).in_dll(L,'dbg_bgo')[:]
        except Exception: pass
    e=np.linalg.norm(est-d['gt'],axis=1)
    bge=np.linalg.norm(bgl-btw,axis=1);bgn=np.linalg.norm(btw,axis=1)
    try:
        st={n_:ctypes.c_double.in_dll(L,n_).value for n_ in ('dbg_sxy','dbg_sxx','dbg_syy','dbg_cnt','dbg_rm','dbg_pr2','dbg_e2','dbg_rv')}
        if os.environ.get('PS'):print(os.path.basename(f),'slope %.2f cnt %.0f rm %.2f rms(pred) %.2e rms(e) %.2e rms(sig) %.2e'%(st['dbg_sxy']/max(st['dbg_sxx'],1e-30),st['dbg_cnt'],st['dbg_rm']/max(st['dbg_cnt'],1),(st['dbg_pr2']/max(st['dbg_cnt'],1))**.5,(st['dbg_e2']/max(st['dbg_cnt'],1))**.5,(st['dbg_rv']/max(st['dbg_cnt'],1))**.5))
    except Exception as ex_: print('EXC',ex_)
    BGD=(np.mean(bgn),np.mean(bge[200:]),np.mean(bge[:200]))
    if DBG:
        Rg=d['Rgt'];R0=Rg[0];ang=[]
        for k in (100,300,600,1199):
            x,y,z,w=qe[k];Re=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            Rt=R0.T@Rg[k];ang.append(np.degrees(np.arccos(np.clip((np.trace(Re.T@Rt)-1)/2,-1,1))))
        print(os.path.basename(f),'att err deg@100,300,600,1199',np.round(ang,1),'ate',e.mean(),'err@100,300,600',e[[100,300,600]].round(1))
    return os.path.basename(f),float(np.sqrt((e**2).mean())),float(np.linalg.norm(np.diff(d['gt'],axis=0),axis=1).sum()),float(e[-1]),BGD
if __name__=='__main__':
    so=build(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else '');fl=sorted(glob.glob('/data/backups/rganapa/Sebastian/gen3/research/e1/cache/*.npz'))[:int(os.environ.get('NFL','20'))]
    with ProcessPoolExecutor(8) as ex: R=list(ex.map(run,[(so,f) for f in fl]))
    a=np.array([r[1] for r in R]);pl=np.array([r[2] for r in R])
    print('ATE mean %.3f med %.3f max %.2f | path mean %.1f | end-err mean %.2f | bg true-norm %.4f err(after 10s) %.4f err(first10s) %.4f'%((a.mean(),np.median(a),a.max(),pl.mean(),np.mean([r[3] for r in R]))+tuple(np.mean([r[4][i] for r in R]) for i in range(3))))
    if '--v' in sys.argv: [print(r) for r in R]
