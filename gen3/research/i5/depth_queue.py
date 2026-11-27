import os,json,glob,zipfile,subprocess,hashlib,csv,time
from pathlib import Path
import sys
sys.path.append('/data/backups/rganapa/Sebastian/venv-teacher/lib/python3.12/site-packages')
from huggingface_hub import hf_hub_download
R=Path('/data/backups/rganapa/Sebastian'); G=R/'gen3'; OUT=G/'research/overnight_20261127/depth'; KEEP=G/'out/keep'; META=G/'out/up'
caps={'room':4,'warehouse':3,'forest':3}; selected=[]; scenes=set(); zips={p.stem:p for p in KEEP.glob('*.zip')}
# Metadata roster supplies split/class/scene; cached local zip supplies val bytes.
for mp in sorted(META.glob('*.json')):
 try:
  m=json.load(open(mp)); id=m['id']; cls=m.get('setting_class'); scene=m.get('scene'); zp=zips.get(id)
  if m.get('split')!='val' or not zp or cls not in caps or caps[cls]<=0 or not scene or scene in scenes: continue
  selected.append((id,str(zp),'val',scene)); scenes.add(scene); caps[cls]-=1
 except Exception: continue
print('VAL_SELECTED',selected,flush=True)
# Export cached validation immediately; this needs no network access.
for id,p,split,scene in list(selected):
 dst=OUT/(id+'.npz')
 if dst.exists(): continue
 subprocess.run(['/data/backups/rganapa/Sebastian/venv-sim11/bin/python','depth_smoke.py',p,str(OUT)],check=True)
 with open(OUT/'manifest.jsonl','a') as f: f.write(json.dumps({'id':id,'split':split,'scene':scene})+'\n')
 print('QUEUE_PROGRESS',id,split,scene,flush=True)
# Existing metadata has verified expected SHA256 and source split. Fetch one TRAIN file at a time.
manifest=hf_hub_download('SentientNapkin/viobench-stage3','manifest.csv',repo_type='dataset')
rows={r['id']:r for r in csv.DictReader(open(manifest))}
tcaps={'room':4,'warehouse':3,'forest':3}; tscenes=set(); temp=R/'tmp/vio_overnight/depth'; downloaded=0
for id in sorted(glob.glob(str(META/'*.json'))):
 m=json.load(open(id)); cls=m.get('setting_class'); scene=m.get('glb') or m.get('scene')
 if m.get('split')!='train' or cls not in tcaps or tcaps[cls]<=0 or not scene or scene in scenes or scene in tscenes: continue
 row=rows.get(m['id']);
 if not row: continue
 if not m.get('glb') or not os.path.isfile(m['glb']): continue
 size=int(m.get('bytes',row.get('bytes',0)) or 0)
 if downloaded+size>8_000_000_000: continue
 p=hf_hub_download('SentientNapkin/viobench-stage3',row['path'],repo_type='dataset',local_dir=str(temp))
 h=hashlib.sha256(open(p,'rb').read()).hexdigest()
 if h!=m.get('sha256'): raise RuntimeError('SHA256 mismatch '+m['id'])
 downloaded+=os.path.getsize(p); tscenes.add(scene); tcaps[cls]-=1
 subprocess.run(['/data/backups/rganapa/Sebastian/venv-sim11/bin/python','depth_smoke.py',p,str(OUT)],check=True)
 with open(OUT/'manifest.jsonl','a') as f: f.write(json.dumps({'id':m['id'],'split':'train','class':cls,'scene':scene,'sha256':h,'zip_bytes':os.path.getsize(p)})+'\n')
 os.remove(p)
 print('QUEUE_PROGRESS',m['id'],'train',scene,'train_download_bytes',downloaded,flush=True)
 if sum(tcaps.values())==0: break
for id,p,split,scene in [x for x in selected if x[2]=='train']:
 dst=OUT/(id+'.npz')
 if dst.exists(): continue
 subprocess.run(['/data/backups/rganapa/Sebastian/venv-sim11/bin/python','depth_smoke.py',p,str(OUT)],check=True)
 with open(OUT/'manifest.jsonl','a') as f: f.write(json.dumps({'id':id,'split':split,'scene':scene,'sha256':hashlib.sha256(open(p,'rb').read()).hexdigest() if split=='train' else None})+'\n')
 if split=='train': os.remove(p)
 print('QUEUE_PROGRESS',id,split,scene,'train_download_bytes',downloaded,flush=True)
