"""Delete local flight zips ONLY when HF has a byte-identical copy (sha256). Logs every file. Never touches holdout/testv2."""
import os,sys,glob,hashlib,json,time
from concurrent.futures import ThreadPoolExecutor
sys.path[:0]=['/data/backups/rganapa/Sebastian/venv-teacher/lib/python3.12/site-packages']
from huggingface_hub import HfApi
R='/data/backups/rganapa/Sebastian/gen/'
DIRS=['raw','raw-fast','raw-bench','raw-servertail','raw-speed','raw-learnvel-st3','raw-rerender','raw-train2']
a=HfApi();hub={}
for s in a.dataset_info('SentientNapkin/viobench-flights',files_metadata=True).siblings:
    if s.lfs: hub.setdefault(os.path.basename(s.rfilename),set()).add(s.lfs.sha256)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<22),b''): h.update(b)
    return h.hexdigest()
files=[z for d in DIRS for z in glob.glob(R+d+'/**/*.zip',recursive=True) if not os.path.islink(z)]
print('candidates',len(files),flush=True)
log=open(R+'../gen3/deletion.log','a');freed=[0];kept=[0];n=[0]
def do(z):
    b=os.path.basename(z)
    if b not in hub: log.write(f'KEEP noname {z}\n');kept[0]+=1;return
    s=sha(z);sz=os.path.getsize(z)
    if s in hub[b]:
        freed[0]+=sz;os.remove(z);log.write(f'DEL {z} {sz} {s}\n')
    else: kept[0]+=1;log.write(f'KEEP sha-mismatch {z} {s}\n')
    n[0]+=1
    if n[0]%500==0: print(n[0],'done freed GB',round(freed[0]/1e9),'kept',kept[0],flush=True);log.flush()
with ThreadPoolExecutor(8) as ex: list(ex.map(do,files))
print('FINISHED freed GB',round(freed[0]/1e9),'deleted',n[0]-kept[0],'kept',kept[0],flush=True);log.flush()
