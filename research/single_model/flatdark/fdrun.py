"""usage: fdrun.py name src.c "DEFINES" [workers] -> builds, runs on flatdark/pool_stress (live<40 | flat/dark>0.05 flights, 3xx), writes table_<name>.json"""
import os,sys,json
os.environ['VIOBENCH_PNG_CACHE']='0'
sys.path.insert(0,'.')
from pathlib import Path
from research.single_model import run_variant as RV
name,src,defs=sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else ''
w=int(sys.argv[4]) if len(sys.argv)>4 else 16
pool=sys.argv[5] if len(sys.argv)>5 else 'research/single_model/flatdark/pool_stress'
name='fd_'+name
wasm=RV.build(Path(src),RV.CMAKE_DEFAULT,defs,name)
sc=RV.run_guest_fast(wasm,pool,RV.OUT/name/'eval',workers=w,name=name)
d=json.load(open(sc)); rows={r['episode']:r.get('ate_full') for r in d['rows']}
json.dump(rows,open(f'research/single_model/flatdark/table_{name}.json','w'))
print(name,'done',len([v for v in rows.values() if v is not None]))
