from pathlib import Path
import json,sys,numpy as np
w=Path(__file__).resolve().parent
name=sys.argv[1]
rng=np.random.default_rng(20261122)
rows=['| set (flights) | GSLV ATE | candidate ATE | delta [scene-bootstrap 95% CI] m | tails >3/5/10 baseline → candidate | peak M (base → candidate) | p99 M (base → candidate) |','|---|---:|---:|---|---|---:|---:|']
summary={}
for pool in ['st2dev','st3','st2conf','fdev','fconf','st1dev','st1conf']:
 B=[];A=[]; F=[]; FB=[]
 for suf in ['', '_r1','_r2']:
  bp=w.parent/'learnvel/tables'/f'glNP{suf}__{pool}.json';ap=w/'tables'/f'{name}{suf}__{pool}.json'
  if not ap.exists():break
  b={r['ep']:r for r in json.loads(bp.read_text())};a={r['ep']:r for r in json.loads(ap.read_text())}
  assert a.keys()==b.keys(), (pool,suf,'flight mismatch')
  ks=sorted(a); assert all(a[k]['ok'] and a[k]['ate_rmse'] is not None and a[k]['filled_frames']==0 for k in ks)
  B.append([b[k]['ate_rmse'] for k in ks]);A.append([a[k]['ate_rmse'] for k in ks])
  for f in (w.parents[1]/f'results/single_model/lj_{name}{suf}'/pool).glob('**/fuel.npy'):F.append(np.load(f))
  for f in (w.parents[1]/f'results/single_model/lv_glNP{suf}'/pool).glob('**/fuel.npy'):FB.append(np.load(f))
 if len(A)!=3:continue
 A=np.array(A);B=np.array(B);delta=(A-B).mean(axis=0)
 sc=[(a[k].get('cat'),a[k].get('scene')) for k in ks];groups={s:np.array([i for i,v in enumerate(sc) if v==s]) for s in sorted(set(sc),key=str)}
 assert len(groups)>1,(pool,'missing scenes')
 idx=list(groups.values());boot=[]
 for _ in range(10000):
  ix=np.concatenate([idx[i] for i in rng.integers(len(idx),size=len(idx))]);boot.append(delta[ix].mean())
 ci=np.percentile(boot,[2.5,97.5]);tail=lambda x:'/'.join(str(int((x>t).sum())) for t in (3,5,10))
 fuels=np.concatenate(F);peak=fuels.max()/1e6;p99=np.percentile(fuels,99)/1e6
 new5pairs=[(int(rep),ks[i]) for rep,i in zip(*np.where((A>5)&(B<=5)))]
 new5=[ks[i] for i in range(len(ks)) if (A[:,i]>5).any() and not (B[:,i]>5).any()]
 bf=np.concatenate(FB);base_peak=bf.max()/1e6;base_p99=np.percentile(bf,99)/1e6
 d=dict(n=len(ks),base=float(B.mean()),arm=float(A.mean()),delta=float(delta.mean()),ci=ci.tolist(),base_tails=tail(B),arm_tails=tail(A),peak=float(peak),p99=float(p99),new5=new5,new5_pairs=new5pairs,base_peak=float(base_peak),base_p99=float(base_p99),reps=3)
 summary[pool]=d
 rows.append(f'| {pool} ({len(ks)}) | {B.mean():.4f} | {A.mean():.4f} | {delta.mean():+.4f} [{ci[0]:+.4f},{ci[1]:+.4f}] | {tail(B)} → {tail(A)} | {base_peak:.3f} → {peak:.3f} | {base_p99:.3f} → {p99:.3f} |')
t='\n'.join(rows)+'\n';print(t);(w/'tables'/f'{name}_final.md').write_text(t);(w/'tables'/f'{name}_final.json').write_text(json.dumps(summary,indent=2)+'\n')
