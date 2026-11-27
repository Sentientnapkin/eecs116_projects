"""Free-yaw sweep: real g3 pipeline (template, camera, crop) minus writing; prints probe-comparable stats."""
import sys,json,time,traceback,numpy as np
sys.argv_=sys.argv;sys.argv=['x'];import g3,viobench.tools.datasets.generate.simulation as S;sys.argv=sys.argv_
import cv2
def run(f):
    g3.set_template(f['task_overrides']);kl=g3.free_yaw_class() if f['regime']=='free-yaw' else S.SimConfig
    sim=kl(instances=1,duration_seconds=f['seconds'],hold_seconds=f['hold_seconds'],waypoints=48,fov=105.,fov_range=30.)
    if f.get('build_only'):
        import hyperdrone;h=sim.render_header(200.0);e=hyperdrone.HyperDrone([g3.ref(f)[f['scene']]],config=hyperdrone.Config(num_worlds=1,spec_header=str(h)),seed=0,parameters={"cameras":{"camera0":{"fov":105.}}});e.close();return {}
    ep,=S.simulate(sim,g3.ref(f),1,seed=f['seed'],camera=g3.camera_for(f),name='fy',log=lambda m:None)
    if f.get('crop_start_s'): ep=g3.crop(ep,f['crop_start_s'])
    m=g3.motion(ep);fr=np.stack([cv2.cvtColor(np.asarray(ep.frames[i]),cv2.COLOR_RGB2GRAY) for i in range(0,len(ep.frames),40)])
    ft=ep.frame_times;g=ep.imu[(ep.imu[:,0]<=ft[min(19,len(ft)-1)]+1e-9),4:7];m['start_gyro_rms']=float(np.sqrt((g**2).sum(1).mean()));m['luma']=float(fr.mean());return m
if __name__=='__main__':
    ro,out,w,n=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
    for f in json.load(open(ro))['flights'][w::n]:
        t=time.time()
        try: r={**f,**run(f),'ok':1}
        except Exception as e: r={**f,'ok':0,'err':repr(e)[:200]};traceback.print_exc()
        r['s']=round(time.time()-t);r.pop('task_overrides',None);open(out,'a').write(json.dumps(r)+'\n')
