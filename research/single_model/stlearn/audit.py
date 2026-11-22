"""Metadata allowlist; no excluded episode/cache payload is opened."""
import hashlib,json,re,collections,random
from pathlib import Path
HERE=Path(__file__).resolve().parent;SM=HERE.parent;ROOT=SM.parents[1];BASE=ROOT.parent
fold=lambda c,s:int(hashlib.sha256(f'{c}:{s}'.encode()).hexdigest()[:8],16)%5
val=lambda c,s:int(hashlib.sha256(f'stlearn-val:{c}:{s}'.encode()).hexdigest()[:8],16)%20==0

def main():
 d=json.load(open(SM/'stlong/tables/data_audit.json'));ho={tuple(v) for v in d['holdout_scenes']};bad=set(d['forbidden_scenes']);eval_ids=set();eval_hash=set();scene_cats=collections.defaultdict(set)
 for r in d['train']+d['val']:scene_cats[r['scene']].add(r['catalog'])
 for c,s in ho:scene_cats[s].add(c)
 for line in (ROOT/'research/campaign/perflight.jsonl').read_text().splitlines():
  r=json.loads(line);eval_ids.add(r['episode']);scene_cats[r['scene']].add(r['catalog'])
 for pool in [BASE/'tmp/st_pools'/p for p in ['st2dev','st2conf','st1dev','st1conf']]+[BASE/'tmp/lv_pools'/p for p in ['st3','fdev','fconf']]:
  for z in pool.glob('*.zip'):
   eval_ids.add(z.stem);p=z.with_suffix('.json')
   if p.exists():
    m=json.load(open(p));scene_cats[m['scene']].add(m['catalog'])
    if m.get('sha256'):eval_hash.add(m['sha256'])
 def allowed(c,s,n='',ph=''):return fold(c,s)!=4 and (c,s) not in ho and s not in bad and n not in eval_ids and ph not in eval_hash
 rows=[];excluded=collections.Counter();seen=set()
 for r0 in d['train']:
  r=dict(r0);c,s,n=r['catalog'],r['scene'],r['name']
  if not allowed(c,s,n):excluded['legacy_eval_or_forbidden']+=1;continue
  r.update(kind='legacy',role='val' if val(c,s) else 'train',file=hashlib.sha256(('legacy:'+n).encode()).hexdigest()+'_legacy.npz');rows.append(r);seen.add(n)
 # stlong files/rows are read only and explicitly recorded; snapshot updated by refresh.py.
 p=SM/'stlong/gen/sl_rows.json'
 if p.exists():
  for n,r0 in json.load(open(p)).items():
   r=dict(r0);c,s=r['catalog'],r['scene'];cache=BASE/'tmp/sl_cache_train'/f'{n}.npz'
   if n in seen or not cache.exists() or not allowed(c,s,n):continue
   r.update(kind='legacy',cache=str(cache),role='val' if val(c,s) else 'train',file=hashlib.sha256(('legacy:'+n).encode()).hexdigest()+'_legacy.npz');rows.append(r);seen.add(n)
 meta=json.load(open(HERE/'tables/teacher-full-labeled.json'));cand=[]
 for arr in meta['datasets'].values():
  if isinstance(arr,list):cand.extend(arr)
 native=json.load(open(HERE/'tables/native-campaign-train-records-1184.json'));cand+=native['records']
 best={}
 for r in cand:
  s=r['scene'];c=r.get('catalog')
  if not c:
   cs=scene_cats.get(s,set());c='procthor' if s.startswith('ProcTHOR') else next(iter(cs)) if len(cs)==1 else None
  if c is None:excluded['hf_unknown_catalog']+=1;continue
  if not allowed(c,s,r.get('flight_id',''),r.get('parent_sha256','')):excluded['hf_forbidden']+=1;continue
  par=r['parent_sha256']
  if par not in best or r['frames']>best[par]['frames']:best[par]=dict(r,catalog=c)
 fs=json.load(open(HERE/'tables/hf_files.json'));fm={Path(f).name:f for f in fs if f.endswith('.npz')}
 for r in best.values():
  if r['file'] not in fm:excluded['hf_missing_file']+=1;continue
  r.update(kind='hf',repo_file=fm[r['file']],name='hf-'+r['parent_sha256'][:20],role='val' if val(r['catalog'],r['scene']) else 'train');rows.append(r)
 (HERE/'work/source_records.json').write_text(json.dumps(rows,indent=1));repro=[r for r in rows if r['kind']=='hf']
 # Original recipe additionally excludes all calibrated scenes; preserve its hash%12 validation.
 selected_scenes={json.loads(l)['scene'] for l in (ROOT/'research/campaign/perflight.jsonl').read_text().splitlines()}
 repro=[r for r in repro if r['scene'] not in selected_scenes]
 for r in repro:r=dict(r)
 (HERE/'work/repro_sources.json').write_text(json.dumps(repro,indent=1))
 summary=dict(existing=len(rows),kinds=dict(collections.Counter(r['kind'] for r in rows)),roles=dict(collections.Counter(r['role'] for r in rows)),excluded=dict(excluded),repro=len(repro),holdout_scenes=sorted(ho),forbidden_scenes=sorted(bad),eval_ids=sorted(eval_ids),eval_hashes=sorted(eval_hash))
 (HERE/'tables/data_audit.json').write_text(json.dumps(summary,indent=1))
 # Port every numeric autopilot override verbatim from styles.txt.
 styles={}
 for line in (ROOT/'eecs116_vio/gpu_kit/styles.txt').read_text().splitlines():
  if line.startswith('#') or '|' not in line:continue
  name,body=line.split('|',1);styles[name.strip()]={k:float(v) for k,v in re.findall(r'static constexpr T (\w+) = ([0-9.]+);',body)}
 scenes=sorted({(r['catalog'],r['scene']) for r in d['train'] if allowed(r['catalog'],r['scene'])})
 tex=json.load(open(SM/'learnvel/tables/scenetex.json'));weights=[1+4*tex.get(c+'|'+s,{}).get('lowfrac',0) for c,s in scenes]
 known=set()
 for sub in ['stlong','learnvel','learned_c']:
  for p in (SM/sub/'gen').glob('roster*.json'):
   z=json.load(open(p))
   known.update(f['seed'] for f in z.get('flights',[]) if 'seed' in f)
 seeds=set(range(9100000,9104000));assert not(seeds&known)
 rng=random.Random(20261122);fl=[];names=list(styles)
 for i in range(4000):
  c,s=rng.choices(scenes,weights)[0];sty=names[i%len(names)];mid=bool((i//len(names))%2)
  f=dict(id=f'stl-{i:05d}-{s}',split='bench',group='stlearn',catalog=c,scene=s,seed=9100000+i,seconds=90 if mid else 60,regime='benchmark',hold_seconds=1.,waypoints_per_second=.8,task_overrides=styles[sty],setting=sty,start='mid' if mid else 'static',role='val' if val(c,s) else 'train')
  if mid:f['crop_start_s']=30.
  fl.append(f)
 (HERE/'gen/roster.json').write_text(json.dumps({'spec':'stlearn styles, scene-heldout 5%, distinct seeds','flights':fl},indent=1))
 print({k:v for k,v in summary.items() if k not in ['holdout_scenes','forbidden_scenes','eval_ids','eval_hashes']},'new roster',len(fl),'seed range',min(seeds),max(seeds))
if __name__=='__main__':main()
