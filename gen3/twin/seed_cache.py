"""python seed_cache.py NAME WASM POOLDIR: copy already-computed per-flight reports of the same wasm sha (any eval name/pool)
into evals/NAME/<pool>/NAME-<sha8>/ so evalpool only runs new flights (results are deterministic per wasm+flight)."""
import sys,os,glob,shutil,hashlib
G='/data/backups/rganapa/Sebastian/gen3'
name,wasm,pool=sys.argv[1:4];sha=hashlib.sha256(open(wasm,'rb').read()).hexdigest()[:8];pn=os.path.basename(pool.rstrip('/'))
dst=f'{G}/evals/{name}/{pn}/{name}-{sha}';n=0
for z in glob.glob(f'{pool}/*.zip'):
    i=os.path.basename(z)[:-4]
    if os.path.exists(f'{dst}/{i}/report/report.json'): continue
    src=glob.glob(f'{G}/evals/*/*/*-{sha}/{i}/report/report.json')
    if src:
        os.makedirs(f'{dst}/{i}',exist_ok=True);shutil.copytree(os.path.dirname(src[0]),f'{dst}/{i}/report',dirs_exist_ok=True);n+=1
print('seeded',n,'for',name,pn)
