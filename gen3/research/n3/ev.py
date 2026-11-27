"""python ev.py NAME WASM POOL [workers=8] -> res/NAME__POOL.json + summary line (also appended res/summary.tsv). Tolerant evalpool."""
import sys,json,os,glob,statistics as s,collections as C
from pathlib import Path
sys.path.insert(0,'/data/backups/rganapa/Sebastian/eecs116_projects'); sys.path.insert(0,'/data/backups/rganapa/Sebastian/gen3/research/n3')
os.environ['VIOBENCH_PNG_CACHE']='0'
from research.single_model import run_variant as RV
from gain import gain
name,wasm,pool=sys.argv[1],Path(sys.argv[2]),Path(sys.argv[3]);W=int(sys.argv[4]) if len(sys.argv)>4 else 8
G=Path('/data/backups/rganapa/Sebastian/gen3');E=G/'research/n3';out=E/'runs'/name/pool.name
sc=RV.run_guest_fast(wasm,pool,out,workers=W,name=name)
rows=json.load(open(sc))['rows'];meta={}
for p in glob.glob(str(G/'out/up/*.json')):
    if 'shards' in p: continue
    try: r=json.load(open(p));meta[r['id']]=r
    except Exception: pass
res=[]
for r in rows:
    m=meta.get(r['episode'],{});res.append({'id':r['episode'],'ate':r.get('ate_full'),'peak':r.get('peak_fuel_per_frame'),'err':r.get('error') or r.get('failure'),**{k:m.get(k) for k in('setting_class','regime','start','start_fwd_speed')}})
(E/'res').mkdir(exist_ok=True);json.dump(res,open(E/'res'/f'{name}__{pool.name}.json','w'))
ok=[r for r in res if r['ate'] is not None]
a=s.mean(r['ate'] for r in ok);pk=max(r['peak'] or 0 for r in ok)
line='%s\t%s\tn=%d/%d\tmean %.3f\tmed %.3f\tpeak %d\tgain %.2f'%(name,pool.name,len(ok),len(res),a,s.median(r['ate'] for r in ok),pk,gain(max(pk,1),a))
print(line);open(E/'res/summary.tsv','a').write(line+'\n')
D=C.defaultdict(list)
for r in ok: D[r['setting_class']].append(r['ate'])
print(' ',{k:'%.2f(n=%d)'%(s.mean(v),len(v)) for k,v in D.items()})
