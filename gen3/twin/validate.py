"""Compare python features (feat_probe30.jsonl) and recorded metadata against the probe decoded locally (probe30/)."""
import json,glob,sys,os,numpy as np
sys.path.insert(0,'/data/backups/rganapa/Sebastian/eecs116_projects/eecs116_vio/probe')
from decode import decode_episode
py={json.loads(l)['id']:json.loads(l) for l in open('feat_probe30.jsonl')}
rows=[]
for r in glob.glob('probe30/probe_reports/*/report-*/report.json'):
    fid=r.split('/')[2]; e=json.load(open(r))['episodes'][0]; d=decode_episode(e)
    if 'camera' not in d: print('nodecode',fid,d['checks']); continue
    m=json.load(open(f'../out/up/{fid}.json')); rows.append((fid,d,py[fid],m))
F=[('hfov',lambda d:d['camera']['hfov_deg'],'hfov_deg','fov_deg'),
 ('start_fwd',lambda d:d['start_forward_speed'],'start_forward_speed','start_fwd_speed'),
 ('start_gyro',lambda d:d['start_1s']['gyro_rms'],'start_gyro_rms',None),
 ('start_acc',lambda d:d['start_1s']['accel_dev_rms'],'start_accel_dev_rms',None),
 ('distance',lambda d:d['path']['distance'],'distance','path_m'),
 ('mean_speed',lambda d:d['path']['mean_speed'],'mean_speed','mean_speed'),
 ('rms_dist',lambda d:d['path']['rms_dist_from_start'],'rms_dist_from_start','rms_dist_from_start'),
 ('spread',lambda d:d['path']['rms_spread'],'rms_spread','rms_spread'),
 ('rms1s',lambda d:d['path']['rms_1s_displacement'],'rms_1s_displacement',None),
 ('gyro_rms',lambda d:d['dynamics']['gyro_rms'],'gyro_rms','gyro_rms'),
 ('yaw_rms',lambda d:d['dynamics']['yaw_rms'],'yaw_rms','yaw_rms'),
 ('jerk',lambda d:d['dynamics']['jerk_rms'],'jerk_rms','jerk_rms'),
 ('accxy',lambda d:d['dynamics']['accel_xy_rms'],'accel_xy_rms',None),
 ('Y',lambda d:d['image']['Y_mean'],'Y_mean','luma_mean'),
 ('chroma_g',lambda d:d['image']['chroma_g'],'chroma_g',None),
 ('chroma_b',lambda d:d['image']['chroma_b'],'chroma_b',None),
 ('grad2',lambda d:d['image']['grad2_mean'],'grad2_mean',None),
 ('Ytop',lambda d:d['image']['Y_top'],'Y_top',None),('Ybot',lambda d:d['image']['Y_bottom'],'Y_bottom',None),
 ('blurx0',lambda d:d['blur_ratio_x_by_px_speed'][0],lambda p:p['blur_x'][0],None),
 ('blurx1',lambda d:d['blur_ratio_x_by_px_speed'][1],lambda p:p['blur_x'][1] if p['blur_nx'][1]>=3 else None,None),
 ('blury0',lambda d:d['blur_ratio_y_by_px_speed'][0],lambda p:p['blur_y'][0],None),
 ('blury1',lambda d:d['blur_ratio_y_by_px_speed'][1],lambda p:p['blur_y'][1] if p['blur_ny'][1]>=3 else None,None)]
print(f'n={len(rows)}  probe vs python: median |rel err|, p90 |rel err|, corr ; probe vs metadata likewise')
for name,g,pk,mk in F:
    a=[];b=[];c=[]
    for fid,d,p,m in rows:
        x=g(d); y=pk(p) if callable(pk) else p[pk]
        z=m.get(mk) if mk else None
        if x is None or y is None: continue
        a.append(x);b.append(y);c.append(z)
    a=np.array(a,float);b=np.array(b,float)
    def st(a,b):
        if len(a)<3: return '-'
        re=np.abs(b-a)/np.maximum(np.abs(a),1e-3 if name!='start_fwd' else 0.1)
        return f'{np.median(re):6.3f} {np.percentile(re,90):6.3f} r={np.corrcoef(a,b)[0,1]:.3f}'
    s2='-'
    if mk:
        cc=np.array([np.nan if v is None else v for v in c],float); ok=np.isfinite(cc); s2=st(a[ok],cc[ok])
    print(f'{name:11s} n={len(a):2d} py: {st(a,b):26s} meta: {s2}')
