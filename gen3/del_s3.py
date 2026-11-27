"""Delete local copies ONLY when HF has a byte-identical copy (sha256): v3/v1 TEST zips in out/keep (viobench-stage3)
and tmp/vf/shards/*.tar (viobench-flights). Logs every file to deletion.log."""
import os,sys,glob,hashlib
from concurrent.futures import ThreadPoolExecutor
from huggingface_hub import HfApi
a=HfApi()
def hub(repo):
    h={}
    for s in a.dataset_info(repo,files_metadata=True).siblings:
        if s.lfs: h.setdefault(os.path.basename(s.rfilename),set()).add(s.lfs.sha256)
    return h
H3=hub('SentientNapkin/viobench-stage3'); HF=hub('SentientNapkin/viobench-flights')
jobs=[(z,H3) for p in ('s3v3te-','s3te-') for z in glob.glob(f'out/keep/{p}*.zip')]+[(z,HF) for z in glob.glob('/data/backups/rganapa/Sebastian/tmp/vf/shards/*.tar')]
print('candidates',len(jobs),flush=True)
log=open('deletion.log','a');st={'freed':0,'del':0,'kept':0}
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<22),b''): h.update(b)
    return h.hexdigest()
def do(j):
    z,H=j;b=os.path.basename(z);s=sha(z);sz=os.path.getsize(z)
    if s in H.get(b,()): os.remove(z);st['freed']+=sz;st['del']+=1;log.write(f'DEL {z} {sz} {s}\n')
    else: st['kept']+=1;log.write(f'KEEP sha-mismatch/missing {z} {s}\n')
with ThreadPoolExecutor(8) as ex: list(ex.map(do,jobs))
log.flush();print('FINISHED freed GB',round(st['freed']/1e9),'deleted',st['del'],'kept',st['kept'],flush=True)
