import os,shutil,hashlib,json,collections
from pathlib import Path
repo=Path('/data/backups/rganapa/Sebastian/eecs116_projects')
dest=repo/'gen3'; sibling=repo.parent/'gen3'
skip={'.git','__pycache__','cache','raw','ep','data','shard','scenes','pilot','smoke','scratch_up','dbg','tmp','out_test','cutoff_checkpoints','valcache','traincache'}
allowed={'.py','.sh','.c','.cc','.cpp','.h','.hpp','.md','.txt','.json','.jsonl','.csv','.yaml','.yml','.toml','.log','.png','.jpg','.svg','.pt','.wasm'}
manifest=[];omitted=collections.Counter()
def copytree(src,dst):
 if not src.exists():return
 for d,ds,fs in os.walk(src,followlinks=False):
  ds[:]=[x for x in ds if x not in skip and not (Path(d)/x).is_symlink()]
  rel=Path(d).relative_to(src)
  if src == sibling/'evals': ds[:]=[]
  for name in fs:
   p=Path(d)/name
   if p.is_symlink():continue
   s=p.stat().st_size
   # Retain build recipes; generated binaries/source copies are reconstructible.
   if 'builds' in rel.parts and name not in {'flags.txt','flags.json','config.json','README.md'}:omitted['generated_build_files']+=1;continue
   if p.suffix not in allowed or s>10_000_000:omitted['bulk_or_other_files']+=1;continue
   if p.suffix in {'.pt','.wasm'} and not ('overnight_20261127' in str(p) or 'loop2/context_results' in str(p) or 'geometric_tokens' in str(p)):omitted['other_generated_models']+=1;continue
   if any(x in name.lower() for x in ['credentials','token.json','.env','private_key']):omitted['credential_like_names']+=1;continue
   t=dst/rel/name;t.parent.mkdir(parents=True,exist_ok=True)
   if not t.exists() or t.stat().st_size != s or abs(t.stat().st_mtime-p.stat().st_mtime)>0.001:shutil.copy2(p,t)
   manifest.append({'path':str(t.relative_to(repo)),'source':str(p),'bytes':s,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
for name in ['research','agents','evals','cfg','pools','twin','twin_hf']:
 copytree(sibling/name,dest/name)
for p in sibling.iterdir():
 if p.is_file() and p.suffix in allowed and p.stat().st_size<2_000_000:
  if p.suffix not in {'.log','.jpg'}:shutil.copy2(p,dest/p.name)
for name in ['vio_overnight','vio_loop3','vio_loop2','vio_fourlane_20261127','vio_research_loop']:
 copytree(Path('/tmp')/name,dest/'archived_prototypes'/name)
copytree(repo.parent/'tmp/vio_loop3/geometric_tokens',dest/'archived_prototypes/geometric_tokens')
# Preserve the exact current best and its source/configuration.
b=dest/'preserved_best';b.mkdir(exist_ok=True)
for s,n in [('scratch_up/gslv_s3_snace6e1.wasm','gslv_s3_snace6e1.wasm'),('agents/anchors/base_sn.c','base_sn.c'),('agents/anchors/builds/snace6e1/flags.txt','flags.txt')]:
 p=sibling/s
 if p.exists():shutil.copy2(p,b/n)
(repo/'gen3/SNAPSHOT_MANIFEST.json').write_text(json.dumps({'files':manifest,'omitted_counts':dict(omitted),'note':'Raw datasets, image/track arrays, caches, generated build copies and large files remain at original locations; checkpoint and result files from the overnight batch are included.'},indent=2)+'\n')
print(json.dumps({'files':len(manifest),'bytes':sum(x['bytes'] for x in manifest),'omitted':dict(omitted)}),flush=True)
