#!/usr/bin/env python3
"""Finite causal clone capacity/fuel Pareto queue on the current anchor."""
import hashlib,json,os,shutil,statistics,subprocess,sys,time,random
from pathlib import Path
G=Path('/data/backups/rganapa/Sebastian/gen3'); ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects')
W=Path('/tmp/vio_overnight/classical'); O=Path('/dev/shm/vio_overnight/classical')
SH=Path('/tmp/vio_loop2/shared'); SRC=G/'agents/anchors/base_sn.c'; CM=ROOT/'research/single_model/linejac/CMakeLists.txt'
BASE=G/'scratch_up/gslv_s3_snace6e1.wasm'; TC=G.parent/'tmp/viobench-toolchain'; NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
BASESHA='1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8'
SRCSHA='b09f81004e37646f32df6f5ba9f0e802ee2a1b9a9caa6b94caf2164c0a37a777'
BASEFLAGS='PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6 EDGE=1 EDGE_MYTH=10.0'
START=time.monotonic(); DEADLINE=START+6*3600
W.mkdir(parents=True,exist_ok=True); O.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def log(s):
 with (W/'status.log').open('a') as f:f.write(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+' '+s+'\n');f.flush()
def build(name,extra=''):
 out=O/'builds'/name/'solution.wasm'; out.parent.mkdir(parents=True,exist_ok=True)
 if out.exists():return out
 sd=O/'builds'/name/'src';sd.mkdir(parents=True,exist_ok=True);shutil.copy2(SRC,sd/'solution.c');shutil.copy2(CM,sd/'CMakeLists.txt')
 flags=' '.join('-D'+x for x in (BASEFLAGS+' '+extra).split()); b=sd/'build'; env=os.environ.copy();env['CMAKE_BUILD_PARALLEL_LEVEL']='2'
 for cmd in (['cmake','-S',str(sd),'-B',str(b),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={flags}'],['cmake','--build',str(b),'-j2']):
  p=subprocess.run(cmd,text=True,capture_output=True,env=env)
  if p.returncode:raise RuntimeError('build failed '+name+' '+p.stdout[-1000:]+p.stderr[-1000:])
 shutil.copy2(b/'solution.wasm',out);return out
def evalone(name,batch,w):
 marker=W/f'{batch}_{name}.json'
 if marker.exists():return json.loads(marker.read_text())
 if time.monotonic()>DEADLINE:raise TimeoutError('queue deadline')
 sys.path.insert(0,str(ROOT));from research.single_model.run_variant import run_guest_fast
 sc=run_guest_fast(w,SH/batch,O/'evals'/batch,workers=4,name='classical_'+name+'_'+batch); rows=json.loads(Path(sc).read_text())['rows']
 exp=len(list((SH/batch).glob('*.zip')))
 if len(rows)!=exp or any(r.get('ate_full') is None or r.get('failure') or r.get('error') for r in rows):raise RuntimeError(f'incomplete {name}/{batch}: {len(rows)}/{exp}')
 vals=[r['ate_full'] for r in rows]; result={'candidate':name,'batch':batch,'sha256':sha(w),'rows':rows,'n':len(rows),'mean_ate':statistics.mean(vals),'median_ate':statistics.median(vals),'worst_ate':max(vals),'peak_fuel':max(r.get('peak_fuel_per_frame',0) or 0 for r in rows),'p95_fuel':max(r.get('p95_fuel_per_frame',0) or 0 for r in rows)}
 marker.write_text(json.dumps(result,indent=2)+'\n');log(f'DONE {batch}/{name} n={len(rows)} mean={result["mean_ate"]:.6f} worst={result["worst_ate"]:.6f} peakfuel={result["peak_fuel"]} p95max={result["p95_fuel"]}');return result
def stats(a,b):
 aa={r['episode']:r['ate_full'] for r in a['rows']};bb={r['episode']:r['ate_full'] for r in b['rows']}
 if aa.keys()!=bb.keys():raise RuntimeError('episode mismatch')
 d=[aa[k]-bb[k] for k in sorted(aa)];rng=random.Random(116); n=len(d); sm=[]
 for _ in range(12000):sm.append(sum(d[rng.randrange(n)] for _ in range(n))/n)
 sm.sort();return {'n':n,'mean_delta':statistics.mean(d),'median_delta':statistics.median(d),'worst_regression':max(d),'improved':sum(x<0 for x in d),'ci95':[sm[int(.025*len(sm))],sm[int(.975*len(sm))-1]]}
def main():
 if sha(SRC)!=SRCSHA or sha(BASE)!=BASESHA:raise RuntimeError('immutable source/artifact SHA mismatch')
 meta={'source':str(SRC),'source_sha256':sha(SRC),'baseline':str(BASE),'baseline_sha256':sha(BASE),'flags':BASEFLAGS,'flags_reference':str(G/'agents/anchors/builds/snace6e1/flags.txt')}
 (W/'identity.json').write_text(json.dumps(meta,indent=2)+'\n')
 # Exact source/flags reproduction first; must match current official artifact byte for byte.
 z=build('zero_control'); zs=sha(z); (W/'zero_control.json').write_text(json.dumps({'expected':BASESHA,'actual':zs,'byte_equal':zs==BASESHA},indent=2)+'\n')
 if zs!=BASESHA:raise RuntimeError('zero-change build differs from current anchor')
 baseline={'screen24':json.loads((SH/'screen24_baseline.json').read_text()),'confirm48':json.loads((SH/'confirm48_baseline.json').read_text())}
 cases=[('g30_c12_o14',30000000,12,14),('g100_c20_o22',100000000,20,22)]
 controls={};screen={};paired={}; promising=[]
 for name,gov,clones,obs in cases:
  ctrl=f'control_g{gov//1000000}_c8'; cand=f'capacity_g{gov//1000000}_c{clones}_o{obs}'
  cw=build(ctrl,f'GOV_B={gov} MAX_CLONES=8 MAX_OBS=10'); vw=build(cand,f'GOV_B={gov} MAX_CLONES={clones} MAX_OBS={obs}')
  if sha(cw)==BASESHA or sha(vw)==BASESHA:raise RuntimeError('changed build unexpectedly equals anchor')
  c=evalone(ctrl,'screen24',cw); v=evalone(cand,'screen24',vw); controls[ctrl]=c; screen[cand]=v
  st=stats(v,c);paired[cand]={'control':ctrl,'screen':st};log(f'SCREEN {cand} '+json.dumps(st))
  if st['mean_delta']<-.01 and st['ci95'][1]<0 and st['worst_regression']<.5:promising.append((cand,ctrl,vw,cw))
 (W/'screen_summary.json').write_text(json.dumps({'controls':controls,'candidates':screen,'paired':paired,'promising':[x[0] for x in promising]},indent=2)+'\n')
 confirmed=[]
 for cand,ctrl,vw,cw in promising:
  cb=evalone(ctrl,'confirm48',cw); vb=evalone(cand,'confirm48',vw); st=stats(vb,cb); (W/f'confirm_{cand}.json').write_text(json.dumps({'candidate':vb,'control':cb,'paired':st},indent=2)+'\n');log(f'CONFIRM {cand} '+json.dumps(st))
  if st['mean_delta']<0 and st['ci95'][1]<0 and st['worst_regression']<.5:confirmed.append(cand)
 (W/'queue.done.json').write_text(json.dumps({'confirmed':confirmed,'promising':[x[0] for x in promising],'elapsed_seconds':time.monotonic()-START},indent=2)+'\n');log('QUEUE COMPLETE')
if __name__=='__main__':
 try:main()
 except BaseException as e:log('ERROR '+repr(e));(W/'queue.error.json').write_text(json.dumps({'error':repr(e),'elapsed_seconds':time.monotonic()-START},indent=2)+'\n');raise
