import sys,ctypes,numpy as np,json,glob
import sim
defs=sys.argv[1];so=sim.build('src/ev1.c',defs+' ORACLE=1 ORVEL=1')
R=[]
for f in sorted(glob.glob('cache/*.npz'))[:10]:
    L=ctypes.CDLL(so);L.step.argtypes=[ctypes.c_double,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int32,ctypes.c_void_p]
    d=np.load(f);cfg=json.dumps({'fx':float(d['fx']),'fy':float(d['fx']),'cx':float(d['cx']),'cy':float(d['cy']),'T_cam_imu':[float(x) for x in d['T']]}).encode();L.init(cfg,len(cfg))
    g=d['g'];imu=np.ascontiguousarray(d['imu']);rgb=np.zeros((240,320,3),np.uint8);out=np.zeros(13)
    T=d['T'].reshape(4,4);Rbc=T[:3,:3].T;Rg=d['Rgt'];Rw0=Rg[0]@Rbc.T
    (ctypes.c_float*3).in_dll(L,'ORG')[:]=list((Rw0.T@np.array([0,0,-9.81])).astype(np.float32))
    gv=np.zeros_like(d['gt']);gv[1:]=(d['gt'][1:]-d['gt'][:-1])/0.05;H=(ctypes.c_float*64).in_dll(L,'DBGH')
    for k in range(1,1200):
        Rb=Rbc@(Rg[0].T@Rg[k])@Rbc.T;(ctypes.c_float*9).in_dll(L,'ORC')[:]=list(Rb.astype(np.float32).ravel())
        (ctypes.c_float*3).in_dll(L,'ORV')[:]=list((Rbc@gv[k]).astype(np.float32))
        for i in range(64): H[i]=0
        rgb[:,:,1]=g[k];L.step(float(d['t'][k]),rgb.ctypes.data,imu[k].ctypes.data,10,out.ctypes.data)
        for i in range(16):
            if H[4*i+3]>0: R.append((abs(H[4*i])/H[4*i+3],np.hypot(H[4*i+1],H[4*i+2]),H[4*i+3]))
R=np.array(R);print(defs,'n',len(R))
for lo,hi in [(0.1,0.3),(0.3,1),(1,3),(3,10),(10,100)]:
    m=(R[:,1]>=lo)&(R[:,1]<hi)
    if m.sum(): print(' flow %g-%g px: n=%d  |h|/|v| med %.3f p90 %.3f'%(lo,hi,m.sum(),np.median(R[m,0]),np.percentile(R[m,0],90)))
