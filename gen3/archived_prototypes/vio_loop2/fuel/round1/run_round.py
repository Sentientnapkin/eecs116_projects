import json,os,shutil,subprocess,hashlib,statistics,time
from pathlib import Path
TASK=Path('/tmp/vio_loop2/fuel/round1'); BULK=Path('/dev/shm/vio_loop2/fuel/round1'); G=Path('/data/backups/rganapa/Sebastian/gen3'); ROOT=G.parent/'eecs116_projects'; SRC=G/'agents/anchors/base_sn.c'; BASESHA='1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8'; SRCSHA='b09f81004e37646f32df6f5ba9f0e802ee2a1b9a9caa6b94caf2164c0a37a777'; FLAGS=(TASK.parent/'control.flags').read_text().strip(); CM=ROOT/'research/single_model/linejac/CMakeLists.txt'; TC=G.parent/'tmp/viobench-toolchain'; NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native'); PY=G.parent/'venv-teacher/bin/python'; SHARED=Path('/tmp/vio_loop2/shared'); OUT=Path('/dev/shm/vio_loop2/shared')
def log(d):
 with (TASK/'status.jsonl').open('a') as f:f.write(json.dumps({'utc':time.strftime('%FT%TZ',time.gmtime()),**d})+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(SRC)!=SRCSHA: raise RuntimeError('SOURCE HASH MISMATCH')
if sha(G/'scratch_up/gslv_s3_snace6e1.wasm')!=BASESHA: raise RuntimeError('BASE WASM MISMATCH')
base=json.load(open(SHARED/'screen24_baseline.json'))
if base['baseline_sha256']!=BASESHA:raise RuntimeError('SCREEN CONTROL HASH MISMATCH')
import sys;sys.path.insert(0,str(ROOT));from research.single_model.run_variant import run_guest_fast
for j in map(json.loads,(TASK/'queue.jsonl').read_text().splitlines()):
 name=j['id']; w=BULK/'builds'/name/'solution.wasm'; d=FLAGS+' '+j['delta']
 if not w.exists():
  sd=w.parent/'src';bd=BULK/'builds'/name/'build';sd.mkdir(parents=True,exist_ok=True);shutil.copy2(SRC,sd/'solution.c');shutil.copy2(CM,sd/'CMakeLists.txt');(w.parent/'flags.txt').write_text(d+'\n')
  cflags=' '.join('-D'+x for x in d.split())
  for cmd in [['cmake','-S',str(sd),'-B',str(bd),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={cflags}'],['cmake','--build',str(bd)]]:
   p=subprocess.run(cmd,capture_output=True,text=True)
   if p.returncode:raise RuntimeError('BUILD '+name+': '+p.stderr[-2500:])
  shutil.copy2(bd/'solution.wasm',w)
 log({'event':'built','id':name,'sha256':sha(w),'flags':d,'bytes':w.stat().st_size})
 scores=run_guest_fast(w,SHARED/'screen24',BULK/'evals'/name,workers=4,name='fuel_'+name)
 rows=json.load(open(scores))['rows']; b={x['episode']:x for x in base['rows']}; rec=[]
 for r in rows:
  q=b.get(r.get('episode'),{});rec.append({'id':r.get('episode'),'ate':r.get('ate_full'),'base_ate':q.get('ate_full'),'peak':r.get('peak_fuel_per_frame'),'base_peak':q.get('peak_fuel_per_frame'),'failure':r.get('failure')})
 good=[x for x in rec if x['ate'] is not None and x['base_ate'] is not None and x['peak'] is not None]
 summ={'id':name,'wasm_sha256':sha(w),'flags':d,'n':len(good),'mean_ate':statistics.mean(x['ate'] for x in good) if good else None,'base_mean_ate':statistics.mean(x['base_ate'] for x in good) if good else None,'paired_delta':statistics.mean(x['ate']-x['base_ate'] for x in good) if good else None,'peak_max':max((x['peak'] for x in good),default=None),'base_peak_max':max((x['base_peak'] for x in good),default=None),'paired_peak_delta_max':max((x['peak']-x['base_peak'] for x in good),default=None),'per_class':{},'records':rec}
 for cls in ['fo','ro','wa']:
  rr=[x for x in good if '-'+cls+'-' in x['id']];summ['per_class'][cls]={'n':len(rr),'ate_delta':statistics.mean(x['ate']-x['base_ate'] for x in rr) if rr else None,'peak_max':max((x['peak'] for x in rr),default=None)}
 (TASK/(name+'.summary.json')).write_text(json.dumps(summ,indent=2)+'\n');log({'event':'evaluated','id':name,'n':summ['n'],'ate':summ['mean_ate'],'paired_delta':summ['paired_delta'],'peak':summ['peak_max'],'base_peak':summ['base_peak_max']})
 # Confirmation is only disjoint and only for screen arms with a material peak reduction and modest mean/tail accuracy cost.
 use=summ['paired_delta'] is not None and summ['paired_delta']<0.01 and summ['peak_max']<=0.99*summ['base_peak_max'] and summ['paired_peak_delta_max']<0.08
 if use:
  cp=SHARED/'confirm48_baseline.json';cb=json.load(open(cp));cs=run_guest_fast(w,SHARED/'confirm48',BULK/'evals'/(name+'_confirm48'),workers=4,name='fuel_'+name+'_confirm48');cr=json.load(open(cs))['rows'];bm={x['episode']:x for x in cb['rows']};paired=[(x,bm.get(x.get('episode'),{})) for x in cr if x.get('ate_full') is not None and x.get('episode') in bm]
  con={'id':name,'n':len(paired),'mean_ate':statistics.mean(x['ate_full'] for x,y in paired),'base_mean_ate':statistics.mean(y['ate_full'] for x,y in paired),'paired_delta':statistics.mean(x['ate_full']-y['ate_full'] for x,y in paired),'peak_max':max(x['peak_fuel_per_frame'] for x,y in paired),'base_peak_max':max(y['peak_fuel_per_frame'] for x,y in paired),'records':[{'id':x['episode'],'ate':x['ate_full'],'base_ate':y['ate_full'],'peak':x['peak_fuel_per_frame'],'base_peak':y['peak_fuel_per_frame']} for x,y in paired]}
  (TASK/(name+'.confirm48.json')).write_text(json.dumps(con,indent=2)+'\n');log({'event':'confirmed','id':name,'n':con['n'],'ate':con['mean_ate'],'paired_delta':con['paired_delta'],'peak':con['peak_max'],'base_peak':con['base_peak_max']})
(TASK/'COMPLETE').write_text('queue exhausted\n');log({'event':'complete'})
