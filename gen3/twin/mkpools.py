"""Build gen3/pools/twin24, gen3/pools/twin120 (symlinks; remote twins downloaded to twin/zips) and twin/pools/v3val120."""
import os,glob,random,time
from huggingface_hub import hf_hub_download
T='/data/backups/rganapa/Sebastian/gen3/twin';G='/data/backups/rganapa/Sebastian/gen3'
def fetch(src):
    if src.startswith('/'): return src
    for k in range(8):
        try: return hf_hub_download('SentientNapkin/viobench-stage3',src[3:],repo_type='dataset',local_dir=f'{T}/zips')
        except Exception as e: print('retry',src,repr(e)[:120],flush=True); time.sleep(120)
    raise RuntimeError(src)
for name in ('twin24','twin120'):
    d=f'{G}/pools/{name}';os.makedirs(d,exist_ok=True)
    want=set()
    for l in open(f'{T}/{name}.txt'):
        e,i,src=l.split()
        want.add(i+'.zip'); p=f'{d}/{i}.zip'
        if not os.path.exists(p):
            z=os.path.realpath(fetch(src))
            if os.path.lexists(p): os.remove(p)
            os.symlink(z,p)
    for f in os.listdir(d):
        if f not in want: os.remove(f'{d}/{f}')
    print(name,len(os.listdir(d)),flush=True)
d=f'{T}/pools/v3val120';os.makedirs(d,exist_ok=True)
if not os.listdir(d):
    zs=sorted(glob.glob(f'{G}/pools/v3val/*.zip'));random.seed(0)
    for z in random.sample(zs,120): os.symlink(os.path.realpath(z),f'{d}/{os.path.basename(z)}')
print('v3val120',len(os.listdir(d)))
