"""Finish the predeclared RA input-attitude comparison, with a common integration attitude.

Uses stored derived inputs only; truth enters scoring, never model inference.
    CUDA_VISIBLE_DEVICES=2 python training_finish_eval.py --policy rolling --output results/eval/training-finish/rolling.json
"""
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
import torch
from odometry_data import load_row,motion_labels
from odometry_eval import load_weights,replay_model,replay_velocities,integrate,metrics

ROOT=Path(__file__).resolve().parent
OLD=Path('/data/backups/rganapa/Sebastian/retrain-attitude-data')
MAIN=Path('/data/backups/rganapa/Sebastian/eecs116_projects/research')
SOURCE=Path('/data/backups/rganapa/Sebastian/eecs116_projects/.claude/worktrees/retrain-attitude/research')
REPAIRED=ROOT/'results/loop/training-finish/kf_grid_native/n2'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def records(policy,roster):
    base=OLD/policy
    if roster=='dev':
        base=REPAIRED if policy=='kf_grid_native' else base/'n2'
        manifest=base/'manifest.json'
        return base,json.loads(manifest.read_text())['datasets']['development'],manifest
    if policy=='rolling':
        if roster=='campaign-dev':base=MAIN/'data/native-campaign/shards';manifest=MAIN/'data/native-campaign/dev-records.json'
        elif roster=='public':base=Path('/data/backups/rganapa/Sebastian/baselines/public-prepared');manifest=base/'records.json'
        else:
            base=MAIN/'data/hub-cache/proxy-val/shards';manifest=OLD/'proxy-val-crop0.json'
    else:base=base/roster;manifest=base/'records.json'
    return base,json.loads(manifest.read_text())['records'],manifest

def label(record,row):
    lab=motion_labels(row['v'],row['times'],row['cam_gt'])
    speed=np.linalg.norm(row['v'][:5],axis=1).mean()
    return {'parent':record.get('parent_sha256') or record.get('parent_file'),'scene':record['scene'],
            'catalog':record.get('catalog'),'crop_s':record.get('crop_s',0),'start':'moving' if record.get('crop_s') else 'static',
            'initial_speed_mps':float(speed),'speed_bin':'above0.1' if speed>.1 else 'at_most0.1',
            'motion':'backward/lateral' if lab['backward'].mean()>.05 or lab['lateral'].mean()>.1 else 'ordinary',
            'frames':len(row['times']),'seconds':float(row['times'][-1]-row['times'][0])}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--policy',choices=['rolling','static08','kf_grid_native'],required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--batch-size',type=int,default=8);ap.add_argument('--seeds',nargs='+',type=int,default=[217,218,219]);ap.add_argument('--rosters',nargs='+',default=['dev','proxy-val','campaign-dev','public']);args=ap.parse_args()
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    policy=args.policy;arm={'rolling':'control','static08':'static08','kf_grid_native':'kfgrid'}[policy]
    runs=[]
    for seed in args.seeds:
        if policy=='rolling' and seed==217:run=SOURCE/'results/loop/RA-N2-control-x3'
        else:run=ROOT/'results/loop'/f'RA-N2-{arm}-x3{("-s"+str(seed)) if seed!=217 else ""}-codexfinish'
        if json.loads((run/'manifest.json').read_text())['status']!='completed':raise RuntimeError(f'Incomplete {run}')
        runs.append((seed,run))
    result={'policy':policy,'source_sha256':{n:sha(ROOT/n) for n in ('training_finish_eval.py','input_attitude.py','attitude_bias.py','odometry_eval.py','odometry_models.py')},
            'causal_inputs':True,'oracle_inputs':False,'fuel':'unmeasured: training/input comparison; not a deployed candidate',
            'weights':{},'datasets':{},'rows':[]}
    nets={seed:replay_model(run,load_weights(run,'best'),'cuda') for seed,run in runs}
    for seed,run in runs:
        result['weights'][str(seed)]={'run':str(run),'sha256':sha(run/'best.safetensors'),'config':json.loads((run/'config.json').read_text())}
    for roster in args.rosters:
        base,recs,manifest=records(policy,roster)
        cache={r['file']:load_row(base,r) for r in recs}
        common_base,common_recs,common_manifest=records('kf_grid_native',roster)
        # Parent+crop keys survive content hashes changing during input derivation.
        key=lambda r:r.get('derived_from',r['sha256'])
        assert len({key(r) for r in recs})==len(recs)
        assert len({key(r) for r in common_recs})==len(common_recs)
        assert all(r.get('parent_sha256') or r.get('parent_file') for r in recs)
        common_recs={key(r):r for r in common_recs}
        common={r['file']:load_row(common_base,common_recs[key(r)]) for r in recs}
        result['datasets'][roster]={'records':len(recs),'parents':len({r.get('parent_sha256') or r.get('parent_file') for r in recs}),'scenes':len({r['scene'] for r in recs}),
                                   'manifest':str(manifest),'sha256':sha(manifest),'common_manifest_sha256':sha(common_manifest)}
        for seed,run in runs:
            velocities=replay_velocities(nets[seed],recs,cache,'cuda',args.batch_size)
            for record in recs:
                row=cache[record['file']];ref=common[record['file']]
                np.testing.assert_allclose(row['times'],ref['times'],atol=1e-6,rtol=0)
                np.testing.assert_array_equal(row['cam_gt'],ref['cam_gt'])
                v=velocities[record['file']];meta={'roster':roster,'seed':seed,'record_id':key(record),**label(record,row)}
                for path,R in [('own',row['R']),('common_kfgrid',ref['R'])]:
                    p=integrate(v,{**row,'R':R});t=row['times']-row['times'][0]
                    for horizon in ('full','30','60'):
                        if horizon=='60' and t[-1]<59.89:continue
                        keep=len(t) if horizon=='full' else int(np.sum(t<=float(horizon)+1e-6))
                        meta[f'{path}_{horizon}']=metrics(p[:keep],row['cam_gt'][:keep],t[:keep],v[:keep],row['v'][:keep])['ate']
                        lab=motion_labels(row['v'][:keep],row['times'][:keep],row['cam_gt'][:keep])
                        meta[f'motion_{horizon}']='backward/lateral' if lab['backward'].mean()>.05 or lab['lateral'].mean()>.1 else 'ordinary'
                meta['velocity_rmse']=float(np.sqrt(np.mean(np.sum((v-row['v'])**2,axis=1))))
                meta['finite_velocity_frames']=int(np.isfinite(v).all(axis=1).sum())
                meta['offline_complete']=bool(np.isfinite(v).all())
                meta['guest_completion_and_filling']='unmeasured: prepared-input replay'
                result['rows'].append(meta)
            print(policy,roster,seed,'finished',flush=True)
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=1)+'\n')
    summary={}
    for roster in args.rosters:
        rr=[r for r in result['rows'] if r['roster']==roster]
        groups={'all':rr}
        for name in ('catalog','start','motion','speed_bin','scene','parent','seed'):
            for value in sorted({str(r[name]) for r in rr}):groups[f'{name}:{value}']=[r for r in rr if str(r[name])==value]
        summary[roster]={g:{**{k:float(np.mean([r[k] for r in rows if k in r])) for k in sorted(set().union(*(r.keys() for r in rows))) if k.startswith(('own_','common_'))}, **{f'replays_{h}':sum(f'own_{h}' in r for r in rows) for h in ('full','30','60')}} for g,rows in groups.items()}
    result['horizon_motion_summary']={roster:{h:{motion:{path:float(np.mean([r[f'{path}_{h}'] for r in result['rows'] if r['roster']==roster and r.get(f'motion_{h}')==motion])) for path in ('own','common_kfgrid') if any(r['roster']==roster and r.get(f'motion_{h}')==motion for r in result['rows'])} for motion in ('ordinary','backward/lateral')} for h in ('30','60','full')} for roster in args.rosters}
    result['summary']=summary;args.output.write_text(json.dumps(result,indent=1)+'\n')
    print(json.dumps({r:v['all'] for r,v in summary.items()},indent=1))
if __name__=='__main__':main()
