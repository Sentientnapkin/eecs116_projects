import sys,ctypes,numpy as np,json,glob
import sim
defs=sys.argv[2];so=sim.build(sys.argv[1],defs);C=[];Zs=[];Z0f=[]
for f in sorted(glob.glob('cache/*.npz'))[:int(sys.argv[3]) if len(sys.argv)>3 else 8]:
    L=ctypes.CDLL(so);L.step.argtypes=[ctypes.c_double,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int32,ctypes.c_void_p]
    d=np.load(f);cfg=json.dumps({'fx':float(d['fx']),'fy':float(d['fx']),'cx':float(d['cx']),'cy':float(d['cy']),'T_cam_imu':[float(x) for x in d['T']]}).encode();L.init(cfg,len(cfg))
    g=d['g'];imu=np.ascontiguousarray(d['imu']);rgb=np.zeros((240,320,3),np.uint8);out=np.zeros(13)
    T=d['T'].reshape(4,4);Rbc=T[:3,:3].T;Rg=d['Rgt'];Rw0=Rg[0]@Rbc.T
    OR='ORACLE' in defs
    if OR:(ctypes.c_float*3).in_dll(L,'ORG')[:]=list((Rw0.T@np.array([0,0,-9.81])).astype(np.float32));(ctypes.c_float*3).in_dll(L,'ORV')[:]=[999,0,0]
    gv=np.zeros_like(d['gt']);gv[1:]=(d['gt'][1:]-d['gt'][:-1])/0.05
    for k in range(1200):
        if OR:Rb=Rbc@(Rg[0].T@Rg[k])@Rbc.T;(ctypes.c_float*9).in_dll(L,'ORC')[:]=list(Rb.astype(np.float32).ravel())
        rgb[:,:,1]=g[k];L.step(float(d['t'][k]),rgb.ctypes.data,imu[k].ctypes.data,10,out.ctypes.data)
        # out twist is cam-frame velocity of cam k ; gv is cam0 axes: rotate gt velocity to cam k axes
        vg=Rg[k].T@Rg[0]@gv[k] if False else None
        ve=out[7:10]  # in cam0 axes (our output uses Rbc^T v_w)
        sg=np.linalg.norm(gv[k]);se=np.linalg.norm(ve)
        if sg>0.3 and k>20: Z0f.append(se<0.05)
        if sg>0.3 and k>20: C.append((float(ve@gv[k]/(sg*se+1e-9)),se/sg,sg))
C=np.array(C);print('frac moving frames |v_est|<0.05:',np.mean(np.array(Z0f)));print(defs,'n',len(C),'cos med %.2f p25 %.2f | |v_est|/|v_gt| med %.2f p25 %.2f p75 %.2f'%(np.median(C[:,0]),np.percentile(C[:,0],25),np.median(C[:,1]),np.percentile(C[:,1],25),np.percentile(C[:,1],75)))
