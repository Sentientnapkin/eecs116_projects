#!/usr/bin/env python3
"""Finite current-MSCKF accuracy queue; all bulk caches live on tmpfs."""
import json, hashlib, os, random, shutil, statistics, subprocess, sys, time
from pathlib import Path

G=Path('/data/backups/rganapa/Sebastian/gen3'); ROOT=G.parent/'eecs116_projects'
W=Path('/tmp/vio_loop2/accuracy'); O=Path('/dev/shm/vio_loop2/accuracy')
SH=Path('/tmp/vio_loop2/shared'); BASE=G/'scratch_up/gslv_s3_snace6e1.wasm'
SRC=G/'agents/anchors/base_sn.c'; CM=ROOT/'research/single_model/linejac/CMakeLists.txt'
TC=G.parent/'tmp/viobench-toolchain'; NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
BASESHA='1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8'
FLAGS='PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4.0 AN_CEF=6 EDGE=1 EDGE_MYTH=10.0'
# Hypotheses: suppress poorly conditioned triangulations; stricter innovation rejection;
# suppress far, weak-parallax landmarks; retain longer feature histories. Each changes a
# different failure mechanism suggested by the long warehouse/forest drift diagnostics.
CAND={
 'tri_cond1':'TRI_MIN_EIG=1e-5',
 'gate_rej1':'CHI2_Z=1.3',
 'depth25v2':'MAX_DEPTH=25.0',
 'obs12v2':'MAX_OBS=12',
}
START=time.monotonic(); DEADLINE=START+7200
W.mkdir(parents=True,exist_ok=True); O.mkdir(parents=True,exist_ok=True)
def log(s):
 with (W/'status.log').open('a') as f:f.write(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+' '+s+'\n');f.flush()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(name,extra=''):
 target=O/'builds'/name/'solution.wasm'; target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists() and name=='same_source_control':return target
 sd=O/'builds'/name/'src';sd.mkdir(parents=True,exist_ok=True)
 shutil.copy2(SRC,sd/'solution.c');shutil.copy2(CM,sd/'CMakeLists.txt')
 if name!='same_source_control':
  sp=sd/'solution.c'; source=sp.read_text()
  source=source.replace('#define TRI_MIN_EIG 1e-6', '#ifndef TRI_MIN_EIG\n#define TRI_MIN_EIG 1e-6\n#endif')
  source=source.replace('#define CHI2_Z 1.645', '#ifndef CHI2_Z\n#define CHI2_Z 1.645\n#endif')
  source=source.replace('chi2_z = 1.645;', 'chi2_z = CHI2_Z;')
  if source.count('#ifndef TRI_MIN_EIG')!=1 or source.count('#ifndef CHI2_Z')!=1 or 'chi2_z = 1.645;' in source:
   raise RuntimeError('candidate source patch failed')
  sp.write_text(source)
 defs=' '.join('-D'+x for x in (FLAGS+' '+extra).split())
 b=sd/'build'; env=os.environ.copy();env['CMAKE_BUILD_PARALLEL_LEVEL']='2'
 for cmd in (['cmake','-S',str(sd),'-B',str(b),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={defs}'],['cmake','--build',str(b),'-j2']):
  p=subprocess.run(cmd,text=True,capture_output=True,env=env)
  if p.returncode:raise RuntimeError('BUILD '+name+': '+p.stdout[-1200:]+p.stderr[-1200:])
 shutil.copy2(b/'solution.wasm',target)
 if name!='same_source_control' and sha(target)==BASESHA:raise RuntimeError(f'{name} was a no-op build')
 return target
def evalone(name,wasm,batch):
 marker=W/f'{batch}_{name}.json'
 if marker.exists():return json.loads(marker.read_text())
 if time.monotonic()>DEADLINE:raise TimeoutError('two-hour wall budget reached')
 sys.path.insert(0,str(ROOT))
 from research.single_model.run_variant import run_guest_fast
 score=run_guest_fast(wasm,SH/batch,O/'evals'/batch,workers=4,name='loop2_'+name+'_'+batch)
 rows=json.loads(Path(score).read_text())['rows']
 if len(rows)!=len(list((SH/batch).glob('*.zip'))) or any(r.get('ate_full') is None or r.get('failure') for r in rows):raise RuntimeError(f'{name}/{batch} incomplete rows={len(rows)}')
 from collections import defaultdict
 scene=defaultdict(list)
 for r in rows:scene[r.get('setting_class','unknown')].append(r['ate_full'])
 result={'candidate':name,'batch':batch,'sha256':sha(wasm),'rows':rows,'n':len(rows),'mean_ate':statistics.mean(r['ate_full'] for r in rows),'median_ate':statistics.median(r['ate_full'] for r in rows),'peak_fuel':max(r.get('peak_fuel_per_frame',0) or 0 for r in rows),'per_scene':{k:{'n':len(v),'mean':statistics.mean(v),'median':statistics.median(v),'p90':sorted(v)[int(.9*(len(v)-1))]} for k,v in scene.items()}}
 marker.write_text(json.dumps(result,indent=2)+'\n');log(f'DONE {batch}/{name} mean={result["mean_ate"]:.6f} peak={result["peak_fuel"]} sha={result["sha256"]}');return result
def paired(a,b):
 aa={r['episode']:r['ate_full'] for r in a['rows']};bb={r['episode']:r['ate_full'] for r in b['rows']}
 if aa.keys()!=bb.keys():raise RuntimeError('paired episode mismatch')
 return [aa[k]-bb[k] for k in sorted(aa)]
def ci(vals,seed=116):
 rng=random.Random(seed);n=len(vals); means=[]
 for _ in range(12000):means.append(sum(vals[rng.randrange(n)] for _ in range(n))/n)
 means.sort();return means[int(.025*len(means))],means[int(.975*len(means))-1]
def stats(a,b):
 d=paired(a,b);lo,hi=ci(d);return {'n':len(d),'mean_delta':statistics.mean(d),'median_delta':statistics.median(d),'ci95':[lo,hi],'max_regression':max(d),'regressions_gt_0_1':sum(x>.1 for x in d)}
def main():
 if sha(BASE)!=BASESHA:raise RuntimeError('immutable baseline hash changed')
 if not (SH/'controls.done').exists():
  log('waiting for orchestrator exact baseline panel controls')
  while not (SH/'controls.done').exists():
   if time.monotonic()>DEADLINE:raise TimeoutError('wait for controls exceeded budget')
   time.sleep(30)
 # Exact-source control build must reproduce artifact byte for byte; also retain an output
 # equality check against root's cached screen control as explicit reproducibility evidence.
 control=build('same_source_control')
 same={'target_sha256':BASESHA,'rebuilt_sha256':sha(control),'byte_equal':sha(control)==BASESHA}
 (W/'same_source_control.json').write_text(json.dumps(same,indent=2)+'\n')
 if not same['byte_equal']:raise RuntimeError('exact same-source control rebuild differs; refusing candidate conclusions')
 baseline=json.loads((SH/'screen24_baseline.json').read_text())
 screens={};passed=[]
 for name,flags in CAND.items():
  res=evalone(name,build(name,flags),'screen24'); ss=stats(res,baseline);screens[name]={'result':res,'paired':ss}
  log('SCREEN '+name+' '+json.dumps(ss))
  if ss['mean_delta']<-.01 and ss['max_regression']<.30:passed.append(name)
 (W/'screen_summary.json').write_text(json.dumps({'screen':screens,'passed':passed,'hypotheses':CAND},indent=2)+'\n')
 confirmed=[]
 for name in passed:
  b=json.loads((SH/'confirm48_baseline.json').read_text())
  r=evalone(name,build(name,CAND[name]),'confirm48');ss=stats(r,b)
  (W/f'confirm_{name}_summary.json').write_text(json.dumps({'result':r,'paired':ss},indent=2)+'\n')
  log('CONFIRM '+name+' '+json.dumps(ss))
  if ss['mean_delta']<0 and ss['ci95'][1]<0 and ss['regressions_gt_0_1']<=5:confirmed.append(name)
 # Test up to three distinct pairwise combos only when both components independently
 # confirm, selected in deterministic order. Screen first, then independent confirmation.
 combos=[]
 for i,a in enumerate(confirmed):
  for b in confirmed[i+1:]:
   if len(combos)>=3:break
   combos.append((a,b))
 if combos:
  cmb_screen={}
  combo_defs={}
  for a,b in combos:
   name=f'combo_{a}__{b}';flags=CAND[a]+' '+CAND[b];combo_defs[name]=flags
   r=evalone(name,build(name,flags),'screen24');ss=stats(r,baseline);cmb_screen[name]={'result':r,'paired':ss}
  (W/'combo_screen.json').write_text(json.dumps(cmb_screen,indent=2)+'\n')
  for name,x in cmb_screen.items():
   if x['paired']['mean_delta']<-.01 and x['paired']['max_regression']<.30:
    r=evalone(name,build(name,combo_defs[name]),'confirm48');ss=stats(r,json.loads((SH/'confirm48_baseline.json').read_text()))
    (W/f'confirm_{name}_summary.json').write_text(json.dumps({'result':r,'paired':ss},indent=2)+'\n')
    log('CONFIRM '+name+' '+json.dumps(ss))
    if ss['mean_delta']<0 and ss['ci95'][1]<0 and ss['regressions_gt_0_1']<=5:confirmed.append(name)
 # Broaden only confirmed promising candidates to full fixed dev evaluation, and v1 regression.
 final=[]
 for name in confirmed[:3]:
  flags=(CAND[name] if name in CAND else combo_defs[name])
  w=build(name,flags)
  for pool,tag in [(G/'pools/v3val','v3val'),(G/'pools/v1val','v1val')]:
   if time.monotonic()>DEADLINE:break
   sys.path.insert(0,str(ROOT))
   from research.single_model.run_variant import run_guest_fast
   score=run_guest_fast(w,pool,O/'evals'/tag,workers=4,name='loop2_'+name+'_'+tag)
   rows=json.loads(Path(score).read_text())['rows']
   rr={'candidate':name,'batch':tag,'sha256':sha(w),'rows':rows,'n':len(rows),'mean_ate':statistics.mean(r['ate_full'] for r in rows if r.get('ate_full') is not None),'median_ate':statistics.median(r['ate_full'] for r in rows if r.get('ate_full') is not None),'peak_fuel':max(r.get('peak_fuel_per_frame',0) or 0 for r in rows)}
   (W/f'{tag}_{name}.json').write_text(json.dumps(rr,indent=2)+'\n');final.append({'candidate':name,'batch':tag,'mean_ate':rr['mean_ate'],'median_ate':rr['median_ate'],'peak_fuel':rr['peak_fuel'],'n':rr['n']})
 (W/'queue.done.json').write_text(json.dumps({'same_source_control':same,'screen_candidates':list(CAND),'confirmed':confirmed,'expanded':final,'elapsed_seconds':time.monotonic()-START},indent=2)+'\n')
 log('QUEUE COMPLETE')
if __name__=='__main__':
 try:main()
 except BaseException as e:
  log('ERROR '+repr(e));(W/'queue.error.json').write_text(json.dumps({'error':repr(e),'elapsed_seconds':time.monotonic()-START},indent=2)+'\n');raise
