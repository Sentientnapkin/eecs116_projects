"""Saved-trajectory evaluation with predeclared scene-disjoint model selection.

Run from repository root with the pinned teacher environment:
  python -m research.guard_fusion.evaluate --workers 48
No training, evaluator edits, private episodes or reserved tests are involved.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np

from .guards import GuardConfig, SOURCE_NAMES, declared_candidates, replay
from .traj import DEFAULT_SELECTED, DEFAULT_RAW, DEFAULT_GUESTS, load_episode, list_episodes
from viobench.tools.runner.metrics import evaluate_trajectory

ROOT = Path(__file__).resolve().parent


def summary(values):
    a = np.asarray(values, float)
    q5,q95 = np.percentile(a,[5,95])
    rng = np.random.default_rng(217)
    draws = a[rng.integers(0,len(a),(5000,12))].mean(1)
    ordered = np.sort(a)
    return {'n':len(a),'mean':float(a.mean()),'median':float(np.median(a)),
        'p90':float(np.percentile(a,90)), 'max':float(a.max()),
        'trimmed95_mean':float(ordered[:max(1,int(.95*len(a)))].mean()),
        'winsorized5_95_mean':float(np.clip(a,q5,q95).mean()),
        'above_5m':int((a>5).sum()),'above_10m':int((a>10).sum()),
        'worst10pct_share':float(ordered[-max(1,int(np.ceil(.1*len(a)))):].sum()/max(a.sum(),1e-12)),
        'bootstrap12_p5_p95':np.percentile(draws,[5,95]).tolist()}


def scene_fold(tags, folds=5):
    scene = str(tags.get('scene'))
    if scene in ('None',''):
        raise ValueError('Missing scene tag: scene-disjoint CV cannot be established')
    key = str(tags.get('catalog',''))+':'+scene
    return int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%folds


def _worker(task):
    selected,raw,episode,guest_map,configs=task
    data=load_episode(selected,raw,episode,guest_map)
    t, truth, sources = data['t'],data['truth'],data['sources']
    singles={s:float(evaluate_trajectory(truth,sources[s]['states'],t).ate_rmse) for s in SOURCE_NAMES}
    for s,value in singles.items():
        expected=data['reference_scores'][s]
        if expected is not None and abs(expected-value)>1e-6:
            raise AssertionError(f'{episode} {s}: reproduced {value} != saved {expected}')
    scores={}
    diagnostics={}
    for cfg in configs:
        T, info=replay(t,sources,cfg,True)
        # Exact headline metric is position RMSE; all returned poses are finite.
        value=float(np.sqrt(np.mean(np.sum((T[:,:3,3]-truth[:,:3])**2,axis=1))))
        if not np.isfinite(value):
            raise ValueError(f'Non-finite output {episode}: {cfg.name}')
        scores[cfg.name]=value
        if cfg.name == configs[0].name:
            diagnostics['first_arm_switches']=int(np.sum(np.diff(np.argmax(info['weights'],axis=1))!=0))
    return {'episode':episode,'tags':data['tags'],'fold':scene_fold(data['tags']),
        'singles':singles,'scores':scores,'diagnostics':diagnostics,
        'filled_frames':{s:sources[s]['filled_frames'] for s in SOURCE_NAMES}}


def select_arm(rows,indices,configs,median_cap=.6,mean_indifference=0.):
    a=np.array([[r['scores'][c.name] for c in configs] for r in rows])[indices]
    means=a.mean(0)
    medians=np.median(a,axis=0)
    eligible=medians<=median_cap
    # The cap is predeclared, and failure to meet it is reported explicitly.
    selection=np.where(eligible,means,np.inf) if eligible.any() else means
    if mean_indifference > 0:
        near_best = selection <= np.min(selection) + mean_indifference
        selected = min(np.where(near_best)[0], key=lambda i:(medians[i],means[i]))
        return int(selected),bool(eligible.any())
    return int(np.argmin(selection)),bool(eligible.any())


def scene_bootstrap_difference(rows,key1,key2,samples=3000):
    # Rows remain grouped by scene, preserving correlated starts/crops.
    grouped={}
    for r in rows:
        group=str(r['tags'].get('catalog'))+':'+str(r['tags']['scene'])
        grouped.setdefault(group,[]).append(r[key1]-r[key2])
    groups=list(grouped.values())
    rng=np.random.default_rng(218)
    vals=[]
    for _ in range(samples):
        draw=rng.integers(0,len(groups),len(groups))
        vals.append(float(np.mean(np.concatenate([groups[i] for i in draw]))))
    return np.percentile(vals,[5,95]).tolist()


def make_report(rows,configs,protocol,mean_indifference=0.):
    report={'protocol':protocol,'metric':'mean_unaligned_ate_m','n':len(rows),
        'singles':{s:summary([r['singles'][s] for r in rows]) for s in SOURCE_NAMES},
        'candidates':{c.name:summary([r['scores'][c.name] for r in rows]) for c in configs},
        'cv':{'folds':[]},'rows':rows}
    oof=np.zeros(len(rows))
    for fold in range(5):
        train=[i for i,r in enumerate(rows) if r['fold']!=fold]
        test=[i for i,r in enumerate(rows) if r['fold']==fold]
        if not train or not test:
            continue
        ix,met=select_arm(rows,train,configs,mean_indifference=mean_indifference)
        chosen=configs[ix]
        for i in test:
            oof[i]=rows[i]['scores'][chosen.name]
            rows[i]['cv_arm']=chosen.name
        report['cv']['folds'].append({'fold':fold,'train_n':len(train),'test_n':len(test),
            'arm':chosen.to_dict(),'training_median_cap_met':met,
            'heldout':summary(oof[test])})
    for i,r in enumerate(rows):
        r['cv_ate']=float(oof[i])
        r['vins_ate']=r['singles']['vins']
        r['n2_ate']=r['singles']['n2']
    cv=report['cv']
    cv.update(summary(oof))
    cv['scene_bootstrap90_vs_vins']=scene_bootstrap_difference(rows,'cv_ate','vins_ate')
    cv['scene_bootstrap90_vs_n2']=scene_bootstrap_difference(rows,'cv_ate','n2_ate')
    cv['fraction_no_worse_than_oracle']=float(np.mean([v<=min(r['singles'].values())+1e-9 for v,r in zip(oof,rows)]))
    cv['fraction_no_worse_than_vins']=float(np.mean([v<=r['singles']['vins']+1e-9 for v,r in zip(oof,rows)]))
    cv['g1']={'mean_at_most_2_2':cv['mean']<=2.2,
        'no_worse_than_oracle_at_least_70pct':cv['fraction_no_worse_than_oracle']>=.7,
        'median_at_most_1_5x_vins':cv['median']<=1.5*report['singles']['vins']['median']}
    cv['g1']['pass']=all(cv['g1'].values())
    cv['low_median_goal_0_6m']=cv['median']<=.6
    cv['splits']={}
    for key in ('group','catalog','start_type'):
        cv['splits'][key]={}
        for label in sorted(set(str(r['tags'].get(key)) for r in rows)):
            idx=[i for i,r in enumerate(rows) if str(r['tags'].get(key))==label]
            cv['splits'][key][label]=summary(oof[idx])
    # Fully disjoint clean confirmation: thresholds selected only outside clean.
    search=[i for i,r in enumerate(rows) if r['tags'].get('group')!='clean']
    holdout=[i for i,r in enumerate(rows) if r['tags'].get('group')=='clean']
    if search and holdout:
        ix,met=select_arm(rows,search,configs,mean_indifference=mean_indifference)
        arm=configs[ix]
        report['clean_confirmation']={'arm':arm.to_dict(),'search_n':len(search),
            'training_median_cap_met':met,'heldout':summary([rows[i]['scores'][arm.name] for i in holdout])}
    report['cv']['failures_above_5m']=[{'episode':r['episode'],'ate':r['cv_ate'],
        'singles':r['singles'],'arm':r['cv_arm']} for r in rows if r['cv_ate']>5]
    ix,met=select_arm(rows,list(range(len(rows))),configs,mean_indifference=mean_indifference)
    report['deployment_candidate']={'status':'exploratory_full_data_refit','arm':configs[ix].to_dict(),
        'training_median_cap_met':met,'summary':report['candidates'][configs[ix].name]}
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selected',type=Path,default=DEFAULT_SELECTED)
    p.add_argument('--raw',type=Path,default=DEFAULT_RAW)
    p.add_argument('--out',type=Path,default=Path('research/results/eval/guard-fusion'))
    p.add_argument('--workers',type=int,default=48)
    p.add_argument('--seed',type=int,choices=[217,218,219],default=217)
    p.add_argument('--limit',type=int)
    p.add_argument('--protocol-version',choices=['v1','v2-safe'],default='v1')
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    configs=declared_candidates()
    if args.protocol_version=='v2-safe':
        configs=[GuardConfig(**dict(c.to_dict(),name=c.name+'-safe')) if c.smooth_s>0 else c for c in configs]
    protocol_path=ROOT/('protocol.json' if args.protocol_version=='v1' else 'protocol-v2-safe.json')
    protocol={'declared_at':datetime.now(timezone.utc).isoformat(),
        'prior_evidence':('report incremental guard grid was previously scored on these flights; new absolute grid not yet scored' if args.protocol_version=='v1' else 'post_hoc_followup: v1 full selected171 scores observed; safe smoothing fixes rejected-source jump injection. No fresh flights.'),
        'metric':'mean_unaligned_ate_m','folds':5,'fold_assignment':'sha256(catalog:scene) first8 modulo5',
        'selection':'minimum training-fold mean among candidates with training median <=0.6m; if none, minimum mean',
        'heldout_clean':'select on non-clean flights only, report clean once',
        'candidates':[c.to_dict() for c in configs]}
    if protocol_path.exists():
        prior=json.loads(protocol_path.read_text())
        if prior['candidates']!=protocol['candidates']:
            raise RuntimeError('Candidate grid changed after declaration; use a new versioned protocol')
        protocol=prior
    else:
        with protocol_path.open('x') as f:
            json.dump(protocol,f,indent=2,allow_nan=False)
    guests=dict(DEFAULT_GUESTS)
    if args.seed!=217:
        guests['n2']={218:'n2_kfinputs_s218-e787620f',219:'n2_kfinputs_s219-0938f841'}[args.seed]
    episodes=list_episodes(args.selected)
    if args.limit:
        episodes=episodes[:args.limit]
    cache=args.out/f'rows-s{args.seed}.json'
    if cache.exists():
        saved=json.loads(cache.read_text())
        if saved['protocol_sha']!=hashlib.sha256(protocol_path.read_bytes()).hexdigest():
            raise RuntimeError('Stale score cache: protocol changed')
        rows=saved['rows']
    else:
        start=time.monotonic()
        tasks=[(args.selected,args.raw,e,guests,configs) for e in episodes]
        rows=[]
        with ProcessPoolExecutor(min(args.workers,64)) as ex:
            for i,row in enumerate(ex.map(_worker,tasks),1):
                rows.append(row)
                if i%20==0 or i==len(tasks):
                    print(f'seed {args.seed}: {i}/{len(tasks)}, {time.monotonic()-start:.1f}s',flush=True)
        cache.write_text(json.dumps({'protocol_sha':hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
            'seed':args.seed,'rows':rows},indent=1))
    if {r['episode'] for r in rows}!=set(episodes):
        raise RuntimeError('Cached episode set differs from requested set')
    report=make_report(rows,configs,protocol)
    report['seed']=args.seed
    (args.out/f'summary-s{args.seed}.json').write_text(json.dumps(report,indent=1,allow_nan=False))
    print(json.dumps({'seed':args.seed,'cv':{k:v for k,v in report['cv'].items() if k not in ('splits','folds')},
        'deployment_candidate':report['deployment_candidate']},indent=2),flush=True)

if __name__=='__main__':
    main()
