"""Apply the predeclared input-attitude gate and preserve scene/parent dependence."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cluster_pair(control,candidate,cluster='scene',key='common_kfgrid_full'):
    a={(r['seed'],r['record_id']):r for r in control}
    pairs=[(a[(r['seed'],r['record_id'])],r) for r in candidate]
    assert len(a)==len(pairs)
    clusters={str(r[cluster]) for _,r in pairs}
    values={c:{'control':float(np.mean([x[key] for x,y in pairs if str(y[cluster])==c])),
               'candidate':float(np.mean([y[key] for x,y in pairs if str(y[cluster])==c]))} for c in sorted(clusters)}
    diffs=np.array([v['candidate']-v['control'] for v in values.values()]);rng=np.random.default_rng(0)
    boot=np.mean(rng.choice(diffs,(4000,len(diffs))),axis=1)
    return {'cluster':cluster,'count':len(values),'per_cluster':values,'mean_cluster_difference':float(np.mean(diffs)),
            'interval90_difference':[float(v) for v in np.percentile(boot,[5,95])],
            'note':'Cluster bootstrap treats training-seed variability separately; per-seed paired scores retained.'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,default=Path('results/eval/training-finish'));args=ap.parse_args()
 files={p:args.directory/f'{p}.json' for p in ('rolling','static08','kf_grid_native')}
 data={p:json.loads(f.read_text()) for p,f in files.items()}
 for d in data.values():assert 'summary' in d
 out={'sources':{p:{'file':str(f),'sha256':sha(f)} for p,f in files.items()},'decision_metric':'mean unaligned ATE',
      'predeclared_gate':'campaign full through common native kf_grid: >=5% improvement, ordinary and both crop groups <=5% regression',
      'deployment_qualified':False,'deployment_limitation':'No raw original-dev/proxy input regeneration/parity; complete native/Wasm path and whole-guest fuel unmeasured.',
      'comparison':{},'scores':{p:{r:s['all'] for r,s in d['summary'].items()} for p,d in data.items()}}
 base=data['rolling']['summary']['campaign-dev'];base_rows=[r for r in data['rolling']['rows'] if r['roster']=='campaign-dev']
 for policy in ('static08','kf_grid_native'):
  candidate=data[policy]['summary']['campaign-dev']
  groups={g:candidate[g]['common_kfgrid_full']/base[g]['common_kfgrid_full']-1 for g in ('all','motion:ordinary','start:static','start:moving')}
  passed=groups['all']<=-.05 and all(groups[g]<=.05 for g in groups if g!='all')
  rows=[r for r in data[policy]['rows'] if r['roster']=='campaign-dev']
  out['comparison'][policy]={'relative_changes':groups,'input_experiment_gate_passed':passed,
      'scene_paired':cluster_pair(base_rows,rows),'parent_paired':cluster_pair(base_rows,rows,'parent'),
      'per_seed':{str(seed):{'control':base[f'seed:{seed}']['common_kfgrid_full'],'candidate':candidate[f'seed:{seed}']['common_kfgrid_full']} for seed in (217,218,219)}}
 args.directory.mkdir(parents=True,exist_ok=True);(args.directory/'decision.json').write_text(json.dumps(out,indent=1)+'\n')
 print(json.dumps({p:{k:v for k,v in d.items() if k in ('relative_changes','input_experiment_gate_passed','per_seed')} for p,d in out['comparison'].items()},indent=1))
 print(json.dumps(out['scores'],indent=1))
if __name__=='__main__':main()
