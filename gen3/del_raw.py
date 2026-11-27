"""Delete gen/raw-{v1gen,eum,holdout} zips ONLY when an HF dataset has a byte-identical copy (sha256). User-authorized 2026-11-26."""
import os,glob,hashlib
from concurrent.futures import ThreadPoolExecutor
from huggingface_hub import HfApi
a=HfApi();H={}
for r in ['viobench-flights','viobench-holdout-240']:
    for s in a.dataset_info('SentientNapkin/'+r,files_metadata=True).siblings:
        if s.lfs: H.setdefault(os.path.basename(s.rfilename),set()).add(s.lfs.sha256)
G='/data/backups/rganapa/Sebastian/gen/'
jobs=[z for d in ['raw-v1gen/bench','raw-eum/bench','raw-holdout/bench','raw-holdout/final'] for z in glob.glob(G+d+'/*.zip')]
print('candidates',len(jobs),flush=True)
log=open('deletion.log','a');st={'freed':0,'del':0,'kept':0}
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<22),b''): h.update(b)
    return h.hexdigest()
def do(z):
    b=os.path.basename(z);s=sha(z);sz=os.path.getsize(z)
    if s in H.get(b,()): os.remove(z);st['freed']+=sz;st['del']+=1;log.write(f'DEL {z} {sz} {s}\n')
    else: st['kept']+=1;log.write(f'KEEP sha-mismatch/missing {z} {s}\n')
with ThreadPoolExecutor(8) as ex: list(ex.map(do,jobs))
log.flush();print('FINISHED freed GB',round(st['freed']/1e9),'deleted',st['del'],'kept',st['kept'],flush=True)
