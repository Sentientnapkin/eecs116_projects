import sys,ctypes,numpy as np,json
sys.argv=['x',sys.argv[1],sys.argv[2],sys.argv[3]]
import sim
so=sim.build(sys.argv[1],sys.argv[2]);f=sys.argv[3]
L=ctypes.CDLL(so);L.step.argtypes=[ctypes.c_double,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int32,ctypes.c_void_p]
d=np.load(f);cfg=json.dumps({'fx':float(d['fx']),'fy':float(d['fx']),'cx':float(d['cx']),'cy':float(d['cy']),'T_cam_imu':[float(x) for x in d['T']]}).encode();L.init(cfg,len(cfg))
g=d['g'];imu=np.ascontiguousarray(d['imu']);rgb=np.zeros((240,320,3),np.uint8);out=np.zeros(13)
T=d['T'].reshape(4,4);Rbc=T[:3,:3].T;Rg=d['Rgt']
if 'ORACLE' in sys.argv[2]:
    Rw0=Rg[0]@Rbc.T;(ctypes.c_float*3).in_dll(L,'ORG')[:]=list((Rw0.T@np.array([0,0,-9.81])).astype(np.float32))
gv=np.gradient(d['gt'],0.05,axis=0)
for k in range(400):
    if 'ORACLE' in sys.argv[2]:
        Rb=Rbc@(Rg[0].T@Rg[k])@Rbc.T;(ctypes.c_float*9).in_dll(L,'ORC')[:]=list(Rb.astype(np.float32).ravel())
    if 'ORVEL' in sys.argv[2]: (ctypes.c_float*3).in_dll(L,'ORV')[:]=list((Rbc@gv[k]).astype(np.float32))
    else: (ctypes.c_float*3).in_dll(L,'ORV')[:]=[999,0,0]
    rgb[:,:,1]=g[k];L.step(float(d['t'][k]),rgb.ctypes.data,imu[k].ctypes.data,10,out.ctypes.data)
    if 'ORVEL' in sys.argv[2] and k%10==0 and k>5: print(k,'h/|v|,fu,fv px',[tuple(np.round((ctypes.c_float*64).in_dll(L,'DBGH')[4*i:4*i+4],3)) for i in range(2)],'v',gv[k].round(2))
    elif k%20==0: print(k,'P00 Sxx Zh',out[10:13],'v_est',out[7:10].round(2),'v_gt',gv[k].round(2),'pos_err',np.linalg.norm(out[:3]-d['gt'][k]).round(2))
