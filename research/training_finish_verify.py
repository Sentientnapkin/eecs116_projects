"""Check matched inference results; correct only roster-count metadata, never inference values."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
base=ROOT/'results/eval/training-finish'
expected={'dev':(14,7),'campaign-dev':(120,60),'proxy-val':(69,68),'public':(10,10)}
reference={}
for policy in ('rolling','static08','kf_grid_native'):
 p=base/f'{policy}.json';d=json.loads(p.read_text());assert 'summary' in d
 original_hash=hashlib.sha256(p.read_bytes()).hexdigest()
 for roster,(records,parents) in expected.items():
  rr=[r for r in d['rows'] if r['roster']==roster]
  assert len(rr)==records*3
  assert len({r['parent'] for r in rr})==parents
  assert all(r['parent'] for r in rr)
  assert len({(r['seed'],r['record_id']) for r in rr})==records*3
  ids={(r['seed'],r['record_id']):(r['parent'],r['scene'],r['crop_s'],r['frames'],r['seconds']) for r in rr}
  if roster in reference:assert ids==reference[roster]
  else:reference[roster]=ids
  assert all(__import__('math').isfinite(r[k]) for r in rr for k in r if k.startswith(('own_','common_')))
  d['datasets'][roster]['parents']=parents
  d['datasets'][roster]['records']=records
 if 'metadata_correction' not in d:
  backup=ROOT/'results/loop/training-finish'/f'{policy}.before-metadata-correction.json'
  shutil.copy2(p,backup)
  d['metadata_correction']={'original_result_sha256':original_hash,'original_result_backup':str(backup),
     'scope':'Correct parent counts after lookup key became original-shard SHA; numeric scores and inference unchanged.',
     'verification_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
  p.write_text(json.dumps(d,indent=1)+'\n')
 print(policy,'matched records/parents/durations/truth conventions, finite metrics: PASS')
