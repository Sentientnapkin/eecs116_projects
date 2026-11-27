"""python evalpool.py NAME WASM POOLDIR [workers] -> per-flight ATE + class summary (gen3/evals/NAME__POOL.json)."""
import sys,json,os,glob,statistics as s,collections as C
from pathlib import Path
sys.path.insert(0,'/data/backups/rganapa/Sebastian/eecs116_projects')
os.environ['VIOBENCH_PNG_CACHE']='0'
from research.single_model import run_variant as RV
name,wasm,pool=sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3]);W=int(sys.argv[4]) if len(sys.argv)>4 else 40
G=Path('/data/backups/rganapa/Sebastian/gen3');out=G/'evals'/name/pool.name
sc=RV.run_guest_fast(wasm,pool,out,workers=W,name=name)
rows=json.load(open(sc))['rows'];meta={}
for p in glob.glob(str(G/'out/up/*.json'))+glob.glob(str(G/'out/ep/*.json')):
    if 'shards' in p: continue
    r=json.load(open(p));meta[r['id']]=r
res=[]
for r in rows:
    m=meta.get(r['episode'],{});res.append({'id':r['episode'],'ate':r.get('ate_full'),'err':r.get('error') or r.get('failure'),'peak':r.get('peak_fuel_per_frame'),**{k:m.get(k) for k in('setting_class','regime','motion_style','start','start_fwd_speed','fov_deg','exposure_s','scene_variant')}})
(G/'evals').mkdir(exist_ok=True);json.dump(res,open(G/'evals'/f'{name}__{pool.name}.json','w'),indent=0)
ok=[r for r in res if r['ate'] is not None];print(name,pool.name,'n',len(ok),'/',len(res),'mean ATE %.3f median %.3f'%(s.mean(r['ate'] for r in ok),s.median(r['ate'] for r in ok)),'>3m',sum(r['ate']>3 for r in ok))
for k in('setting_class','regime','start'):
    D=C.defaultdict(list)
    for r in ok: D[r[k]].append(r['ate'])
    print(' ',k,{a:f'{s.mean(v):.3f} (n={len(v)})' for a,v in sorted(D.items(),key=lambda x:str(x[0]))})
