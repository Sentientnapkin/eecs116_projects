import os, json, hashlib, time, fcntl
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/data/hub-cache')
WORK=Path('/tmp/vio_storage_20261127'); START=time.monotonic(); DEADLINE=START+3600
lock=(WORK/'dedupe.lock').open('w'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
groups=defaultdict(list)
for p in ROOT.glob('**/shards/*.npz'):
 if p.is_symlink(): continue
 s=p.stat(); groups[(p.name,s.st_size)].append(p)

def checksum(p):
 before=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 after=p.stat()
 if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise RuntimeError('file changed')
 return h.hexdigest(),after

def process(item):
 (name,size),paths=item
 if time.monotonic()>DEADLINE:return dict(skipped='deadline',name=name)
 canonical=paths[0]; freed=0; linked=0;errors=[]
 if len(paths)<2:return dict(unique=True)
 try:
  digest,cs=checksum(canonical)
  if digest+'.npz'!=name: raise RuntimeError('canonical content-address mismatch')
  for p in paths[1:]:
   if time.monotonic()>DEADLINE:break
   s=p.stat()
   if (s.st_dev,s.st_ino)==(cs.st_dev,cs.st_ino):continue
   hd,ps=checksum(p)
   if hd!=digest:errors.append(dict(path=str(p),error='checksum mismatch'));continue
   now=p.stat()
   if (now.st_ino,now.st_mtime_ns,now.st_size)!=(ps.st_ino,ps.st_mtime_ns,ps.st_size):continue
   tmp=p.with_name(p.name+'.dedupe-'+str(os.getpid()))
   try:
    os.link(canonical,tmp)
    os.replace(tmp,p)
   finally:
    if tmp.exists():tmp.unlink()
   # Other hardlinks to the displaced inode may retain its allocation.
   if ps.st_nlink==1:freed+=ps.st_blocks*512
   linked+=1
  return dict(name=name,linked=linked,reclaimed_bytes=freed,errors=errors)
 except Exception as e:return dict(name=name,error=repr(e))

total=0;n=0;fail=0
with (WORK/'dedupe.jsonl').open('a',buffering=1) as log, ThreadPoolExecutor(max_workers=4) as pool:
 for result in pool.map(process,groups.items()):
  if not result.get('unique'):
   log.write(json.dumps(result)+'\n');total+=result.get('reclaimed_bytes',0);n+=result.get('linked',0);fail+=bool(result.get('error') or result.get('errors'))
  (WORK/'status.json').write_text(json.dumps(dict(reclaimed_bytes=total,linked_files=n,error_groups=fail,elapsed_seconds=time.monotonic()-START,cap_bytes=600_000_000_000)))
(WORK/'dedupe.done').write_text('bounded checksum-verified deduplication pass finished\n')
