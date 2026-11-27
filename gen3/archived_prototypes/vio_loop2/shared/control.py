import sys,json,hashlib,subprocess,os,statistics
from pathlib import Path
from collections import defaultdict
G=Path('/data/backups/rganapa/Sebastian/gen3');ROOT=G.parent/'eecs116_projects'
W=Path('/tmp/vio_loop2/shared');O=Path('/dev/shm/vio_loop2/shared');W.mkdir(exist_ok=True,parents=True);O.mkdir(exist_ok=True,parents=True)
B=G/'scratch_up/gslv_s3_snace6e1.wasm'; SHA='1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8'
if hashlib.sha256(B.read_bytes()).hexdigest()!=SHA:raise RuntimeError('baseline changed')
old=json.loads(Path('/tmp/vio_fourlane_20261127/accuracy/manifest.json').read_text())
exclude={Path(x).stem for k in ['screen','confirm'] for x in old[k]}
exclude|=set(Path('/tmp/vio_fourlane_20261127/fuel/panel12.tsv').read_text().split())
buckets=defaultdict(list)
for p in (G/'agents/anchors/pools/v3val').glob('*.zip'):
 m=G/'out/up'/(p.stem+'.json')
 if p.stem in exclude or not m.exists():continue
 r=json.loads(m.read_text());buckets[(r['setting_class'],r['start'])].append(p)
manifest={'baseline_sha256':SHA,'excluded_previous_current_system_panels':sorted(exclude),'panels':{},'note':'Development split only; confirmation is disjoint flights, not a pristine scene-level holdout.'}
for key,rows in buckets.items():
 rows.sort(key=lambda p:hashlib.sha256(('vio-loop2-fixed-'+p.stem).encode()).hexdigest())
 if len(rows)<12:raise RuntimeError(f'insufficient {key}: {len(rows)}')
 for batch,arr in [('screen24',rows[:4]),('confirm48',rows[4:12])]:
  d=W/batch;d.mkdir(exist_ok=True)
  for p in arr:
   q=d/p.name
   if not q.exists():q.symlink_to(p)
for batch,n in [('screen24',24),('confirm48',48)]:
 files=sorted((W/batch).glob('*.zip'))
 if len(files)!=n:raise RuntimeError('invalid panel count')
 manifest['panels'][batch]=[p.stem for p in files]
if set(manifest['panels']['screen24'])&set(manifest['panels']['confirm48']):raise RuntimeError('overlap')
mp=W/'manifest.json'
if mp.exists() and json.loads(mp.read_text())!=manifest:raise RuntimeError('manifest mismatch')
mp.write_text(json.dumps(manifest,indent=2)+'\n')
sys.path.insert(0,str(ROOT))
from research.single_model.run_variant import run_guest_fast
for batch in ['screen24','confirm48']:
 done=W/(batch+'_baseline.json')
 if done.exists():continue
 scores=run_guest_fast(B,W/batch,O/'baseline_evals'/batch,workers=4,name='loop2_current_'+batch)
 rows=json.loads(Path(scores).read_text())['rows']
 if len(rows)!=len(manifest['panels'][batch]) or any(r.get('ate_full') is None or r.get('failure') for r in rows):raise RuntimeError('incomplete control')
 result={'baseline_sha256':SHA,'batch':batch,'rows':rows,'mean_ate':statistics.mean(r['ate_full'] for r in rows),'median_ate':statistics.median(r['ate_full'] for r in rows),'peak_fuel':max(r['peak_fuel_per_frame'] for r in rows)}
 done.write_text(json.dumps(result,indent=2)+'\n')
 print(batch,result['mean_ate'],result['peak_fuel'],flush=True)
(W/'controls.done').write_text('both exact-current controls complete\n')
