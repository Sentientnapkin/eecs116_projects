"""dbgw.py WASM FLIGHT.npz : run via wasmtime on cache flight; print net meas error vs GT body vel, att err, ATE"""
import sys,json,numpy as np,ctypes
sys.path.insert(0,'/dev/shm/sebastian-vio/viobench')
import wasmtime
from viobench.tools.runner.engine import make_config
wasm,f=sys.argv[1],sys.argv[2]
cfg=make_config();cfg.epoch_interruption=False
e=wasmtime.Engine(cfg);m=wasmtime.Module.from_file(e,wasm)
s=wasmtime.Store(e);li=wasmtime.Linker(e);li.define_wasi();s.set_wasi(wasmtime.WasiConfig());inst=li.instantiate(s,m);ex=inst.exports(s)
s.set_fuel(10**13)
if '_initialize' in ex: ex['_initialize'](s)
d=np.load(f)
js=json.dumps({'width':320,'height':240,'fx':float(d['fx']),'fy':float(d['fx']),'cx':float(d['cx']),'cy':float(d['cy']),'T_cam_imu':[float(x) for x in d['T']]}).encode()
mem=ex['memory'];
def put(b):
    p=ex['alloc'](s,len(b));mem.write(s,b,p);return p
pj=put(js);assert ex['init'](s,pj,len(js))==0
N=len(d['g']);po=ex['alloc'](s,13*8);
rgb=np.zeros((240,320,3),np.uint8);pf=ex['alloc'](s,rgb.nbytes);pi=ex['alloc'](s,70*8)
T=d['T'].reshape(4,4);Rbc=T[:3,:3].T;Rg=d['Rgt'];gt=d['gt']
est=np.zeros((N,3));rows=[];fu=[]
# gt cam0 position -> body velocity: v_cam0 = diff; body(IMU) vel = Rbc @ Rcam^T v_cam0 (approx ignoring lever)
for k in range(N):
    rgb[:]=d['g'][k][:,:,None];mem.write(s,rgb.tobytes(),pf);mem.write(s,np.ascontiguousarray(d['imu'][k]).tobytes(),pi)
    f0=s.get_fuel();ex['step'](s,float(d['t'][k]),pf,pi,10,po);fu.append(f0-s.get_fuel())
    o=np.frombuffer(mem.read(s,po,po+104),dtype=np.float64);est[k]=o[:3]
    if o[10]<1e8:
        kk=min(k,N-2);vc=(gt[kk+1]-gt[max(kk-1,0)])/(0.1);Rc=Rg[k]@Rbc.T if False else None
        # Rgt = R(q)@Rbc per e1 notes: R(q)=cam rotation in cam0; body vel = Rbc @ R(q)^T v_cam0
        Rq=Rg[k]@Rbc.T;vb=Rbc@Rq.T@vc  # IMU-frame velocity
        rows.append((k,np.array(o[10:13]),vb))
np.savez('/dev/shm/n2_dbg.npz',rows=np.array([[r[0],*r[1]] for r in rows]),gt=gt,Rg=Rg,T=d['T'])
e_=np.linalg.norm(est-gt,axis=1)
err=np.array([r[1]-r[2] for r in rows]);print('ATE %.2f  net meas err rms/axis'%e_.mean(),np.sqrt((err**2).mean(0)).round(2),'|v|gt rms',np.sqrt((np.array([r[2] for r in rows])**2).mean()).round(2))
print('fuel peak',max(fu),'mean',int(np.mean(fu)),'p95',int(np.percentile(fu,95)))
print('est err@100,300,600,1199',e_[[100,300,600,1199]].round(1))
for r in rows[:4]+rows[40:42]:print(r[0],r[1].round(2),r[2].round(2))
fu=np.array(fu[1:]);print('phase max/mean by (k-1)%5 [epoch phase 0]:',[(int(fu[i::5].max()),int(fu[i::5].mean())) for i in range(5)])
