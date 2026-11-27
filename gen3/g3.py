"""Stage-3 flight generator (native viobench episode zips). python g3.py ROSTER OUT WORKER WORKERS ; resumable.
FoV U(75,135) and brightness U(0.6,1.4) are the simulator's own per-episode draws; exposure U(0,50 ms): k=ceil(e/5ms)
200 Hz renders averaged per frame (linear light or sRGB, per flight). Mid-flight starts crop the first C s (frames copied, not re-encoded)."""
import sys,os,json,time,math,traceback,hashlib,io,tarfile,dataclasses
from pathlib import Path
from dataclasses import asdict
R='/data/backups/rganapa/Sebastian/';sys.path[:0]=[R+'eecs116_projects/research']
import numpy as np,cv2
cv2.setNumThreads(1)
import viobench.tools.datasets.generate.simulation as S
from viobench.tools.datasets.storage import write_episode
from viobench.tools.datasets.episode import Episode,FrameSequence
ORIG={'Warehouse':'conta:77d055df9fe567fd73201bd925647a65851b0642','Forest':'conta:edc4844529111a92755b95b3d845d61bb1faa04c'}
BRIGHT=0.4
STOCK=Path(S.__file__).with_name('hyperdrone_world.h.in')
def set_template(over):
    t=STOCK.read_text();a="        static constexpr T BRIGHTNESS_RANDOMIZATION_RANGE = 0;";assert a in t;t=t.replace(a,f"        static constexpr T BRIGHTNESS_RANDOMIZATION_RANGE = {BRIGHT!r};")
    anc="        static constexpr TI INITIALIZATION_HOLD_STEPS";assert anc in t
    t=t.replace(anc,"".join(f"        static constexpr T {k} = {float(v)!r};\n" for k,v in sorted(over.items()))+anc,1)
    p=Path(os.environ.get('TMPDIR','/tmp'))/f"g3world_{hashlib.sha256(t.encode()).hexdigest()[:10]}.h.in"
    if not p.exists(): q=p.with_suffix(f'.{os.getpid()}');q.write_text(t);q.replace(p)
    S.TEMPLATE=p
import hyperdrone
_LAST={}
_ip=hyperdrone.HyperDrone.instance_parameters
def _wrap(self,*a,**k):
    r=_ip(self,*a,**k);_LAST['p']=r;return r
hyperdrone.HyperDrone.instance_parameters=_wrap
L=np.arange(4096)/4095.;LIN=np.where(L<=.04045,L/12.92,((L+.055)/1.055)**2.4).astype(np.float32)
def camera_for(f):
    e=f['exposure_s'];k=min(10,max(1,math.ceil(e/.005-1e-9)));lin=f['blur_space']=='linear';gain=float(f.get('gain',1.0))
    def develop(r,rng):
        if gain!=1.0:
            m=LIN[np.clip(r*4095+.5,0,4095).astype(np.int32)];m=(m.mean(0) if lin else LIN[np.clip(r.mean(0)*4095+.5,0,4095).astype(np.int32)])*gain;m=np.minimum(m,1.0)
            x=np.where(m<=.0031308,12.92*m,1.055*np.power(np.maximum(m,1e-9),1/2.4)-.055)
        elif k==1: x=r[-1]
        elif lin:
            m=LIN[np.clip(r*4095+.5,0,4095).astype(np.int32)].mean(0);x=np.where(m<=.0031308,12.92*m,1.055*np.power(np.maximum(m,1e-9),1/2.4)-.055)
        else: x=r.mean(0)
        return np.clip(np.rint(x*255.),0,255).astype(np.uint8)
    return lambda rng,hz:(k,develop,{'exposure_sampled_s':e,'blur_space':f['blur_space'],'linear_gain':gain})
_hv=None
def ref(f):
    global _hv
    if f['scene'] in ORIG: return {f['scene']:ORIG[f['scene']]}
    if f.get('glb'): return {f['scene']:f['glb']}
    if f['catalog']=='hssd-val':
        _hv=_hv or S.hssd_scenes('val');return {f['scene']:_hv[f['scene']]}
    return S.scene_references([f['scene']])
def crop(e,start):
    k=int(np.searchsorted(e.frame_times,e.frame_times[0]+start-1e-9));shift=e.frame_times[k]-e.frame_times[0];t0=e.frame_times[k]-e.frame_interval-1e-6
    imu=e.imu[e.imu[:,0]>t0].copy();imu[:,0]-=shift;gt=e.ground_truth[e.ground_truth[:,0]>=t0-.02].copy();gt[:,0]-=shift
    c=json.loads(json.dumps(e.config));n=e.num_frames-k;c['episode']['num_frames']=int(n);F=e.frames
    fr=FrameSequence(lambda i,F=F,k=k:F[k+i],n,F.frame_shape,F.dtype,(lambda i,F=F,k=k:F.encoded(k+i)) if F.encoded else None)
    o=Episode(name=e.name,config=c,frame_times=e.frame_times[k:]-shift,frames=fr,imu=imu,ground_truth=gt,T_body_camera=e.T_body_camera,
              meta={a:b for a,b in e.meta.items() if a not in('hash','path')}|{'crop_start_s':start});o.check_consistency();return o
def motion(ep):
    imu=ep.imu;ft=ep.frame_times;n=min(1130,len(ft));m=imu[:,0]<=ft[n-1]+1e-9;g=imu[m,4:7];a=imu[m,1:4];k=(len(a)//10)*10;fa=a[:k].reshape(-1,10,3).mean(1)
    gt=ep.ground_truth;gt=gt[gt[:,0]>=ft[0]-1e-9];p=gt[:,1:4];d=float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum());dur=float(gt[-1,0]-gt[0,0])
    from viobench.tools.geometry import quaternion_to_matrix
    q=gt[0,4:8];Rw=quaternion_to_matrix(q);v0=(gt[min(4,len(gt)-1),1:4]-gt[0,1:4])/max(gt[min(4,len(gt)-1),0]-gt[0,0],1e-6);Rc=Rw@ep.T_body_camera[:3,:3]
    return dict(path_m=d,duration_s=dur,mean_speed=d/max(dur,1e-6),gyro_rms=float(np.sqrt((g**2).sum(1).mean())),yaw_rms=float(np.sqrt((g[:,2]**2).mean())),tilt_rms=float(np.sqrt((g[:,:2]**2).sum(1).mean())),
                jerk_rms=float(np.sqrt(np.mean(np.sum((np.diff(fa,axis=0)/.05)**2,1)))),rms_dist_from_start=float(np.sqrt(((p-p[0])**2).sum(1).mean())),rms_spread=float(np.sqrt(((p-p.mean(0))**2).sum(1).mean())),
                start_speed=float(np.linalg.norm(v0)),start_fwd_speed=float((Rc.T@v0)[2]),extent_m=np.ptp(p,axis=0).round(3).tolist())
def mini(ep,path):
    off=[0];buf=[]
    for i in range(len(ep.frames)):
        g=cv2.cvtColor(np.asarray(ep.frames[i]),cv2.COLOR_RGB2GRAY);b=cv2.imencode('.jpg',cv2.resize(g,(320,240),interpolation=cv2.INTER_AREA),[cv2.IMWRITE_JPEG_QUALITY,95])[1].tobytes();buf.append(b);off.append(off[-1]+len(b))
    npy=lambda a:(lambda f:(np.save(f,a),f.getvalue())[1])(io.BytesIO())
    return {'.imu.npy':npy(np.asarray(ep.imu)),'.gt.npy':npy(np.asarray(ep.ground_truth)),'.frame_times.npy':npy(np.asarray(ep.frame_times)),'.jpg_offsets.npy':npy(np.array(off)),'.jpg.bin':b''.join(buf)},np.stack([cv2.cvtColor(np.asarray(ep.frames[i]),cv2.COLOR_RGB2GRAY) for i in range(0,len(ep.frames),60)])

FY=dict(AMIN=0.2,AMAX=1.2,WMIN=0.2,WMAX=0.9)
def free_yaw_class():
    import re,hyperlux
    from hashlib import sha256
    class FreeYaw(S.SimConfig):
        """Camera heading decoupled from travel: yaw = route_yaw + offset + A sin(w t + phase); offset, A, w, phase are drawn per flight
        from a hash of its random route (no recompile per value). Pace is not slowed by heading misalignment."""
        def render_header(self,imu_rate_hz):
            base=super().render_header(imu_rate_hz)
            hd=Path(hyperlux.__file__).parent/"_vendor/rl-tools/include/rl_tools/rl/environments/hyperdrone/tasks/visual_inertial_localization"
            text=(hd/"tracking_operations_cpu.h").read_text()
            desired="const T desired_yaw = math::atan2(device.math, forward[1], forward[0]);";pace="pace *= alignment * alignment;"
            assert text.count(desired)==1 and text.count(pace)==1
            W=lambda i,j:f"instance_parameters.waypoints[{i}][{j}]"
            H=lambda a,b,c:f"([&](){{ const T x_ = math::sin(device.math, (T){a}*{W(2,0)} + (T){b}*{W(2,1)} + (T){c}*{W(3,0)}) * (T)43758.5453; return x_ - math::floor(device.math, x_); }}())"
            text=text.replace(desired,f"""const T route_yaw = math::atan2(device.math, {W(1,1)} - {W(0,1)}, {W(1,0)} - {W(0,0)});
                    const T fy_off = (T)6.28318530718 * {H(12.9898,78.233,37.719)};
                    const T fy_amp = (T){FY['AMIN']} + (T){FY['AMAX']-FY['AMIN']} * {H(39.346,11.135,83.155)};
                    const T fy_w = (T){FY['WMIN']} + (T){FY['WMAX']-FY['WMIN']} * {H(73.156,52.235,9.151)};
                    const T fy_ph = (T)6.28318530718 * {H(27.191,61.371,45.827)};
                    const T elapsed = (T)world.task_step * dt;
                    const T desired_yaw = route_yaw + fy_off + fy_amp * math::sin(device.math, fy_w * elapsed + fy_ph);""")
            text=text.replace(pace,"(void)alignment;")
            text=re.sub(r'#include "([^"]+)"',lambda m:f'#include "{(hd/m[1]).resolve()}"',text)
            orig="#include <rl_tools/rl/environments/hyperdrone/tasks/visual_inertial_localization/operations_cpu.h>"
            b=base.read_text();assert b.count(orig)==1;spec=b.replace(orig,text+"\n"+orig)
            out=base.parent/f"free-yaw-{sha256(spec.encode()).hexdigest()[:12]}.h"
            if not out.exists(): p=out.with_name(out.name+f".{os.getpid()}.partial");p.write_text(spec);p.replace(out)
            return out
    return FreeYaw
def one(f,out):
    set_template(f['task_overrides'])
    kl=S.SimConfig
    if f.get('regime')=='independent-yaw':
        from robust_sim import IndependentYaw as kl
    elif f.get('regime')=='free-yaw': kl=free_yaw_class()
    sim=kl(instances=1,duration_seconds=f['seconds'],hold_seconds=f['hold_seconds'],waypoints=48,fov=105.,fov_range=30.)
    ep,=S.simulate(sim,ref(f),1,seed=f['seed'],camera=camera_for(f),name=f['setting_class'],log=lambda m:None)
    bs=float(_LAST['p'][0]['render']['brightness_scale']);ep.check_consistency()
    if f.get('crop_start_s'): ep=crop(ep,f['crop_start_s'])
    ep=dataclasses.replace(ep,name=f['id'],meta={**ep.meta,'flight':{k:v for k,v in f.items() if k!='task_overrides'},'task_overrides':f['task_overrides'],'brightness_scale':bs});ep.config['episode']['name']=f['id']
    if not np.isfinite(ep.ground_truth).all() or not np.isfinite(ep.imu).all(): raise ValueError('non-finite')
    pt=out/'partial';pt.mkdir(exist_ok=True,parents=True);p=pt/(f['id']+'.zip');write_episode(ep,p)
    parts,fr=mini(ep,p);mo=motion(ep)
    rec={**{k:v for k,v in f.items() if k!='task_overrides'},'task_overrides':f['task_overrides'],'frames':len(ep.frames),'fov_deg':ep.config['camera']['horizontal_fov_degrees'],'exposure_s':ep.config['episode']['exposure_seconds'],
         'brightness_scale':bs,'linear_gain':float(f.get('gain',1.0)),**mo,'luma_mean':float(fr.mean()),'dark_fraction':float((fr.mean((1,2))<20).mean()),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
         'simulator':asdict(sim),'simulator_class':kl.__name__,'versions':S._versions(),'viobench_commit':'e173f4a'}
    t=out/'ep';t.mkdir(exist_ok=True,parents=True)
    with tarfile.open(t/(f['id']+'.mini.tar.part'),'w') as tf:
        for s,b in [('.json',json.dumps(rec).encode())]+list(parts.items()):
            ti=tarfile.TarInfo(f['id']+s);ti.size=len(b);tf.addfile(ti,io.BytesIO(b))
    os.rename(t/(f['id']+'.mini.tar.part'),t/(f['id']+'.mini.tar'));(t/(f['id']+'.json')).write_text(json.dumps(rec));p.rename(t/(f['id']+'.zip'));return rec
def main():
    ro,out,w,n=sys.argv[1],Path(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4])
    import shutil; out.mkdir(parents=True,exist_ok=True)
    for f in json.load(open(ro))['flights'][w::n]:
        while shutil.disk_usage(out).free<80e9: time.sleep(60)
        if (out/'STOP').exists(): return
        if (out/'ep'/(f['id']+'.json')).exists() or (out/'up'/(f['id']+'.done')).exists(): continue
        t=time.time();st='ok'
        try: one(f,out)
        except Exception as e: st=f'failed: {e!r}'[:250];traceback.print_exc()
        with open(out/'log.jsonl','a') as h: h.write(json.dumps(dict(id=f['id'],status=st,s=round(time.time()-t,1),w=w))+'\n')
if __name__=="__main__": main()
