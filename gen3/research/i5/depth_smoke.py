import os, sys, json, time
import numpy as np
from rr import Flight, make_renderer
from hyperlux.camera import RGB, Depth
import conta, hyperlux

zp=sys.argv[1]; out=sys.argv[2]
os.makedirs(out,exist_ok=True)
f=Flight(zp); scene=f.scene if f.scene.endswith('.glb') else conta.resolve(f.scene)
assert os.path.exists(scene), scene
t=time.time(); sc=hyperlux.load_scene(scene,fidelity='high',preserve_instances=True)
r=make_renderer(160,120,20,[RGB('float32'),Depth()]); r.init(sc)
ids=np.linspace(30,len(f.ft)-31,20,dtype=int)
r.set_cameras(np.stack([f.cam_row(r,f.ft[i]) for i in ids])); r.render(); r.synchronize()
o={type(d).__name__:h for d,h in r.outputs.items()}
rgb=o['RGB'].read()[..., :3].copy(); dep=o['Depth'].read().copy()
assert rgb.shape==(20,120,160,3) and dep.shape==(20,120,160), (rgb.shape,dep.shape)
print('render stats',rgb.shape,dep.shape,'rgb finite',np.isfinite(rgb).mean(),'depth finite',np.isfinite(dep).mean(),'positive',np.mean(dep>0),'depth minmax',np.nanmin(dep),np.nanmax(dep),flush=True)
assert np.isfinite(rgb).all() and (np.isfinite(dep)&(dep>0)).any()
sx=160/f.cfg['image']['width']; sy=120/f.cfg['image']['height']
K=np.array([[f.K[0,0]*sx,0,(f.K[0,2]+.5)*sx-.5],[0,f.K[1,1]*sy,(f.K[1,2]+.5)*sy-.5],[0,0,1]])
poses=[]
for i in ids:
    R,p=f.cam_world(f.ft[i]); poses.append(np.vstack([np.column_stack([R,p]),[0,0,0,1]]))
poses=np.stack(poses)
np.savez_compressed(os.path.join(out,f.ep['name']+'.npz'),rgb=np.clip(rgb*255+.5,0,255).astype('uint8'),depth=dep.astype('float16'),valid=np.isfinite(dep)&(dep>0),K=K,T_wc=poses,timestamps=f.ft[ids])
json.dump({'id':f.ep['name'],'scene':f.scene,'n':len(ids),'rgb_shape':list(rgb.shape),'depth_shape':list(dep.shape),'valid_fraction':float((np.isfinite(dep)&(dep>0)).mean()),'scene_load_s':time.time()-t,'exposure_s':f.meta.get('exposure_s'),'label_timing':'sharp mid-exposure render','depth_units':'meters; optical-axis z; inf invalid'},open(os.path.join(out,f.ep['name']+'.json'),'w'),indent=2)
print('OK',f.ep['name'],f.scene,dep.shape,float((np.isfinite(dep)&(dep>0)).mean()),flush=True)
