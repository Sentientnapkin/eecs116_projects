"""CPU-only direct A160ft diagnostics on the fixed 18-flight local screen panel."""
import importlib.util,json,sys,time,argparse
from pathlib import Path
import numpy as np
import torch

torch.set_num_threads(4)
G=Path('/data/backups/rganapa/Sebastian/gen3')
OUT=Path('/tmp/vio-research-20261126/root')
spec=importlib.util.spec_from_file_location('v4research',G/'agents/netv2/tools/lv4.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
R=G/'agents/netv2/runs/A160ft'
cfg=json.loads((R/'result.json').read_text())
from argparse import Namespace
a=Namespace(**cfg['args'])
net=M.make_net(a).eval()
net.load_state_dict(torch.load(R/'best.pt',map_location='cpu',weights_only=True))
full='--full' in sys.argv
panel=json.loads(Path('/tmp/vio-research-20261126/geometry/panel.json').read_text())
if full:
    meta={}
    for p in (G/'out/up').glob('s3v3va*.json'):
        r=json.loads(p.read_text());meta[r['id']]=r
    panel=[dict(id=p.stem,setting_class=meta[p.stem]['setting_class']) for p in sorted((G/'agents/net/cache/val').glob('*.npz')) if p.stem in meta]
files=[G/'agents/net/cache/val'/f"{r['id']}.npz" for r in panel]
assert all(p.exists() for p in files)
data=M.D(files,'cpu',(0,));starts=data.starts()
t=time.time()
with torch.no_grad():mu,lv,y=M.predict(net,data,starts,bs=128)
mu,lv,y=[x.numpy() for x in (mu,lv,y)];err=mu-y
sp=np.linalg.norm(y,axis=1);predsp=np.linalg.norm(mu,axis=1)
angle=np.degrees(np.arccos(np.clip((mu*y).sum(1)/np.maximum(predsp*sp,1e-9),-1,1)))
z=err/np.exp(lv/2)
def stats(sel):
    e=err[sel];p=sp[sel];q=predsp[sel];ang=angle[sel];moving=p>.3
    return dict(n=int(sel.sum()),mean_norm=float(np.linalg.norm(e,axis=1).mean()),
        rmse_norm=float(np.sqrt((e*e).sum(1).mean())),signed_bias=e.mean(0).tolist(),
        rmse_axes=np.sqrt((e*e).mean(0)).tolist(),
        mean_absolute_speed_error=float(np.abs(q-p).mean()),signed_speed_bias=float((q-p).mean()),
        direction_mean_deg=float(ang[moving].mean()),direction_median_deg=float(np.median(ang[moving])),
        zrms_axes=np.sqrt((z[sel]**2).mean(0)).tolist(),
        coverage1=float((abs(z[sel])<1).mean()),coverage2=float((abs(z[sel])<2).mean()))
res={'scope':f'{len(panel)} validation flights, phase0, all adjacent five-frame-spaced anchor pairs; CPU inference. Body axes FLU; body z is not gravity vertical when tilted.',
     'model_sha_source':str(R/'best.pt'),'elapsed_seconds':time.time()-t,'all':stats(np.ones(len(sp),bool)),
     'fast':stats(sp>1.5),'by_scene':{}}
ids=data.fid[starts].numpy()
for c in ['room','warehouse','forest']:
 mask=np.isin(ids,[i for i,r in enumerate(panel) if r['setting_class']==c]);res['by_scene'][c]=stats(mask)
suffix='_full' if full else ''
np.savez_compressed(OUT/f'model_predictions{suffix}.npz',mu=mu,logvar=lv,target=y,flight_index=ids)
(OUT/f'model_diagnostics{suffix}.json').write_text(json.dumps(res,indent=2))
print(json.dumps(res,indent=2))
