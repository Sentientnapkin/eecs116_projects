"""Predeclared frozen-velocity calibration interventions; dev split only."""
import argparse, hashlib, json
from pathlib import Path
import cv2
import numpy as np
import torch
from common import Flight
from odometry_data import load_row,motion_labels
from odometry_eval import integrate, replay_model, replay_velocities, load_weights
from orientation import Orientation

def rotations(times, packets, images, cfg, mode):
    state=Orientation({**cfg,'policy':'none' if mode=='none' else 'rolling'})
    out=[]; previous=None
    for t,packet,image in zip(times,packets,images):
        difference=0. if previous is None else np.abs(image.astype(np.float32)-previous).mean()/255
        previous=image.astype(np.float32)
        out.append(state.step(float(t),packet,float(difference)))
        if mode=='first' and state.activated: state.cfg={**state.cfg,'policy':'none'}
    return np.stack(out),{'accepted_at':state.accepted_at,'bias_final':state.bias.tolist(),'checked':state.checked_windows}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--raw-dev',type=Path,required=True);p.add_argument('--limit',type=int);p.add_argument('--device',default='cuda');a=p.parse_args()
    cv2.setNumThreads(1);torch.set_num_threads(2);a.output.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(Path('data/hub-cache/B-D0-ssm-x3-gpu/manifests/teacher-full.json').read_text())['sensor_config']
    records=json.loads(Path('data/native-campaign/dev-records.json').read_text())['records'];assert all(r['split']=='dev' for r in records)
    if a.limit: records=records[:a.limit]
    cache={r['file']:load_row(Path('data/native-campaign/shards'),r) for r in records}
    names=['B-D0-ssm-x3-gpu','B-D0-ssm-x3-s218-gpu','B-D0-ssm-x3-s219-gpu'];vel=[];hashes={}
    for name in names:
        run=Path('results/loop')/name; hashes[name]=hashlib.sha256((run/'best.safetensors').read_bytes()).hexdigest()
        vp=a.output/(name+'-velocities.npz')
        if vp.exists():
            with np.load(vp) as z: vel.append({k:z[k] for k in z.files})
        else:
            net=replay_model(run,load_weights(run,'best'),a.device)
            pred=replay_velocities(net,records,cache,a.device,4);np.savez(vp,**pred);vel.append(pred);del net
        print('velocities ready',name,flush=True)
    results=[];parity=[]
    for rec in records:
        row=cache[rec['file']];f=Flight(a.raw_dev/Path(rec['parent_file']).name,crop=rec['crop_s'])
        if len(f.ft)!=len(row['times']) or not np.allclose(f.ft,row['times'],atol=1e-6): raise ValueError('timestamps differ')
        images=row['images'][:,0];rots={};diags={}
        for mode in ('control','none','first'):
            rots[mode],diags[mode]=rotations(f.ft,f.win,images,cfg,mode)
        discrepancy=float(np.max(np.abs(rots['control']-row['R'])));parity.append(discrepancy)
        if discrepancy>1e-6: raise ValueError(f'control reconstruction discrepancy {discrepancy}')
        # A shortened replay must yield the exact same attitude prefix.
        n=min(len(f.ft),201)
        for mode in rots:
            prefix,_=rotations(f.ft[:n],f.win[:n],images[:n],cfg,mode)
            assert np.array_equal(prefix,rots[mode][:n])
        lab=motion_labels(row['v'],row['times'],row['cam_gt'])
        for i,name in enumerate(names):
            for mode,R in rots.items():
                position=integrate(vel[i][rec['file']],{**row,'R':R});error=np.sum((position-row['cam_gt'])**2,axis=1)
                for horizon in (30,60,'full'):
                    if horizon==60 and row['times'][-1]<60-.11: continue
                    relative_times=row['times']-row['times'][0]
                    keep=np.ones(len(error),dtype=bool) if horizon=='full' else relative_times<=horizon+1e-6
                    horizon_labels=motion_labels(row['v'][keep],relative_times[keep],row['cam_gt'][keep])
                    results.append({'file':rec['file'],'parent':rec['parent_sha256'],'scene':rec['scene'],'catalog':rec['catalog'],'crop_s':rec['crop_s'],'start':'nominal' if rec['crop_s']==0 else 'crop5','start_speed':float(np.linalg.norm(row['v'][0])),'speed_bin':'above0.1' if np.linalg.norm(row['v'][0])>.1 else 'at_most0.1','motion':'hard' if horizon_labels['backward'].mean()>.05 or horizon_labels['lateral'].mean()>.1 else 'ordinary','run':name,'mode':mode,'horizon':str(horizon),'ate':float(np.sqrt(error[keep].mean())),'frames':int(keep.sum()),'offline_velocity_frames_finite':bool(np.isfinite(vel[i][rec['file']]).all()),'diagnostic':diags[mode]})
        (a.output/'rows.partial.json').write_text(json.dumps(results))
        print('replayed',rec['file'],discrepancy,flush=True)
    summary={}
    for horizon in ('30','60','full'):
        selected=[r for r in results if r['horizon']==horizon];groups={'all':selected}
        for key in ('run','catalog','motion','start','speed_bin','scene','parent'):
            for value in sorted({r[key] for r in selected}): groups[key+':'+value]=[r for r in selected if r[key]==value]
        summary[horizon]={key:{mode:float(np.mean([r['ate'] for r in group if r['mode']==mode])) for mode in ('control','none','first')} for key,group in groups.items()}
    gates={}
    for mode in ('none','first'):
        gates[mode]=all(summary[h]['all'][mode]<=.9*summary[h]['all']['control'] and all(v[mode]<=1.05*v['control'] for k,v in summary[h].items() if k.startswith(('catalog:','motion:ordinary','start:'))) for h in ('30','full'))
    report={'source_pin':'9b1b07906aff5a3e6f00155e7aecf967d90aa960','checkpoint_sha256':hashes,'max_control_R_discrepancy':max(parity),'causal_prefix_exact':True,'exploratory_gates':gates,'deploy_qualified':False,'fuel':'unmeasured: frozen-input attitude-only diagnostic','horizons':'30 caps all replays incl 25sec crop;60 includes only continuous60sec available;full all replays. Motion bins recomputed per horizon.','summary':summary,'rows':results}
    (a.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'gates':gates,'all':{h:s['all'] for h,s in summary.items()}},indent=2),flush=True)
if __name__=='__main__': main()
