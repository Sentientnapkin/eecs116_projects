"""Post-hoc median-objective policy, with its own immutable declaration and OOF report.

The inference grid and saved scores are unchanged. Selection is performed on
training scenes only within each fold, but the family was designed after seeing
v1/v2; fresh-scene confirmation is still needed. Run with python -m ... .
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np
from .evaluate import make_report, summary
from .guards import GuardConfig


def main():
    root=Path(__file__).resolve().parent
    base=Path('research/results/eval/guard-fusion/v2-safe')
    out=Path('research/results/eval/guard-fusion/v3-median')
    out.mkdir(parents=True,exist_ok=True)
    primary=json.loads((root/'protocol-v2-safe.json').read_text())
    protocol_path=root/'protocol-v3-median.json'
    protocol={'declared_at':datetime.now(timezone.utc).isoformat(),
      'status':'post_hoc_followup; fresh confirmation required',
      'prior_evidence':'all v1/v2 selected171 scores already observed; user explicitly prioritizes lower median',
      'selection':'minimum training-fold median among candidates within0.02m of the minimum training mean, after training median<=0.6m filter; tie lower mean',
      'mean_indifference_m':.02,'folds':5,'fold_assignment':primary['fold_assignment'],
      'candidates':primary['candidates']}
    if protocol_path.exists():
        protocol=json.loads(protocol_path.read_text())
    else:
        with protocol_path.open('x') as f:
            json.dump(protocol,f,indent=2,allow_nan=False)
    configs=[GuardConfig(**c) for c in protocol['candidates']]
    reports=[]
    for seed in (217,218,219):
        cached=json.loads((base/f'rows-s{seed}.json').read_text())
        if cached['seed']!=seed:
            raise ValueError('Score cache seed mismatch')
        rows=cached['rows']
        if any(set(r['scores'])!={c.name for c in configs} for r in rows):
            raise ValueError('Score cache candidate grid mismatch')
        report=make_report(rows,configs,protocol,mean_indifference=.02)
        report['seed']=seed
        (out/f'summary-s{seed}.json').write_text(json.dumps(report,indent=1,allow_nan=False)+'\n')
        reports.append(report)
    # Refit choice based on all three seeds, explicitly exploratory. Treat each
    # flight once, averaging its error across fallback seeds for stable selection.
    pooled=[]
    for i,ref in enumerate(reports[0]['rows']):
        assert all(r['rows'][i]['episode']==ref['episode'] for r in reports)
        row=dict(ref)
        row['scores']={c.name:float(np.mean([r['rows'][i]['scores'][c.name] for r in reports])) for c in configs}
        row['singles']={s:float(np.mean([r['rows'][i]['singles'][s] for r in reports])) for s in ref['singles']}
        pooled.append(row)
    pooled_report=make_report(pooled,configs,protocol,mean_indifference=.02)
    fixed=pooled_report['deployment_candidate']['arm']
    selected={'status':'exploratory_post_hoc_full_data_three_seed_refit','arm':fixed,
        'three_seed_mean':float(np.mean([r['candidates'][fixed['name']]['mean'] for r in reports])),
        'three_seed_median_mean':float(np.mean([r['candidates'][fixed['name']]['median'] for r in reports])),
        'seeds':{str(r['seed']):r['candidates'][fixed['name']] for r in reports}}
    (root/'selected_config_median.json').write_text(json.dumps(selected,indent=2)+'\n')
    result={'protocol':protocol,'selected_config':selected,
       'cv':{str(r['seed']):{k:v for k,v in r['cv'].items() if k not in ('splits','failures_above_5m')} for r in reports},
       'three_seed_cv_mean':float(np.mean([r['cv']['mean'] for r in reports])),
       'three_seed_cv_median_mean':float(np.mean([r['cv']['median'] for r in reports])),
       'pooled_three_seed_cv':{k:v for k,v in pooled_report['cv'].items() if k not in ('splits','failures_above_5m')},
       'clean_confirmation':{str(r['seed']):r.get('clean_confirmation') for r in reports}}
    (out/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'three_seed_cv_mean':result['three_seed_cv_mean'],
        'three_seed_cv_median_mean':result['three_seed_cv_median_mean'],
        'seeds':{r['seed']:{'mean':r['cv']['mean'],'median':r['cv']['median'],
          'fold_arms':[(f['fold'],f['arm']['name']) for f in r['cv']['folds']]} for r in reports},
        'selected_config':selected},indent=2))

if __name__=='__main__':
    main()
