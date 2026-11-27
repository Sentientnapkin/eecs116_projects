#!/usr/bin/env python3
"""Resumable bounded accuracy lane: test faster adaptation of adaptive clone spacing.
Screen: 18 matched v3val flights (3 per scene x start bucket); confirmation: disjoint 18.
Outputs and evaluator caches stay under /dev/shm/vio_fourlane_20261127/accuracy.
"""
import os, sys, json, time, hashlib, shutil, subprocess, statistics
from pathlib import Path
ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects')
GEN=ROOT.parent/'gen3'
BASE=GEN/'scratch_up/gslv_s3_snace6e1.wasm'
SRC=GEN/'agents/anchors/base_sn.c'
CM=ROOT/'research/single_model/linejac/CMakeLists.txt'
TC=ROOT.parent/'tmp/viobench-toolchain'
NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
POOL=GEN/'agents/anchors/pools/v3val'
WORK=Path('/tmp/vio_fourlane_20261127/accuracy')
OUT=Path('/dev/shm/vio_fourlane_20261127/accuracy')
SUB=OUT/'pools'
VENV=ROOT.parent/'venv-teacher/bin/python'
PY=sys.executable
FLAGS=('PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 '
       'INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 '
       'AN_DTH=4.0 AN_CEF=6 EDGE=1 EDGE_MYTH=10.0')
EXPS=[('baseline',None),('da025','AN_DA=0.25'),('da040','AN_DA=0.4')]
START=time.monotonic()

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def log(msg):
    with (WORK/'worker.log').open('a') as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime())+' '+msg+'\n'); f.flush()
def wait_load():
    while float(Path('/proc/loadavg').read_text().split()[0])>170:
        log('loadavg>170; pausing'); time.sleep(60)
def make_pools():
    SUB.mkdir(parents=True,exist_ok=True)
    for batch in ('screen','confirm'):
        d=SUB/batch; d.mkdir(parents=True,exist_ok=True)
        if len(list(d.glob('*.zip'))) == 18: continue
        for stale in d.glob('*.zip'):
            if stale.is_symlink(): stale.unlink()
        buckets={}
        for p in sorted(POOL.glob('*.zip')):
            meta=GEN/'out/up'/(p.stem+'.json')
            if not meta.exists(): continue
            m=json.loads(meta.read_text()); scene=str(m.get('setting_class','')).lower(); start=m.get('start','')
            if scene not in ('room','warehouse','forest'): continue
            # Exclude the tuning set from confirmation: one deterministic alternate seed block.
            key=(scene, 'hover' if 'hover' in start.lower() else 'mid')
            buckets.setdefault(key,[]).append(p)
        # 3 per scene/start, two disjoint six-way groups = 36 total per complete paired batch.
        ix=0 if batch=='screen' else 3
        for key,arr in buckets.items():
            if len(arr)<ix+3: raise RuntimeError(f'not enough flights in {key}: {len(arr)}')
            for p in arr[ix:ix+3]: (d/p.name).symlink_to(p)
        n=len(list(d.glob('*.zip')))
        if n!=18: raise RuntimeError(f'{batch} subset expected 18, got {n}; buckets={[(k,len(v)) for k,v in buckets.items()]}')
    manifest={'baseline_sha256':sha(BASE),'source_sha256':sha(SRC),'screen':[p.name for p in sorted((SUB/'screen').glob('*.zip'))],
      'confirm':[p.name for p in sorted((SUB/'confirm').glob('*.zip'))], 'experiments':EXPS,
      'budget_seconds':3600,'workers':4,'datasets':'gen3 frozen v3val only'}
    mp=WORK/'manifest.json'
    if mp.exists() and json.loads(mp.read_text())!=json.loads(json.dumps(manifest)): raise RuntimeError('manifest changed; refusing mixed resume')
    mp.write_text(json.dumps(manifest,indent=2)+'\n')

def build(exp,da):
    if exp=='baseline': return BASE
    target=OUT/'builds'/exp/'solution.wasm'; target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): return target
    srcdir=OUT/'builds'/exp/'src'; srcdir.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SRC,srcdir/'solution.c'); shutil.copy2(CM,srcdir/'CMakeLists.txt')
    defs=' '.join('-D'+x for x in (FLAGS+' '+da).split())
    b=srcdir/'build'
    r=subprocess.run(['cmake','-S',str(srcdir),'-B',str(b),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={defs}'],capture_output=True,text=True)
    if r.returncode: raise RuntimeError('cmake configure: '+r.stdout[-1000:]+r.stderr[-1000:])
    r=subprocess.run(['cmake','--build',str(b),'-j2'],capture_output=True,text=True)
    if r.returncode: raise RuntimeError('cmake build: '+r.stdout[-1000:]+r.stderr[-1000:])
    shutil.copy2(b/'solution.wasm',target); return target

def evalone(exp,wasm,batch):
    marker=WORK/f'{batch}_{exp}.done.json'
    if marker.exists(): return json.loads(marker.read_text())
    wait_load()
    sys.path.insert(0,str(ROOT))
    from research.single_model.run_variant import run_guest_fast
    name=f'acc_{batch}_{exp}'
    score=run_guest_fast(wasm,SUB/batch,OUT/'evals'/batch,workers=4,name=name)
    rows=json.loads(Path(score).read_text())['rows']
    vals=[r['ate_full'] for r in rows if r.get('ate_full') is not None]
    if len(vals)!=18: raise RuntimeError(f'{batch}/{exp} incomplete: {len(vals)}/18')
    result={'experiment':exp,'batch':batch,'wasm_sha256':sha(wasm),'n':len(vals),'mean_ate':statistics.mean(vals),
            'median_ate':statistics.median(vals),'max_peak_fuel':max(r.get('peak_fuel_per_frame',0) or 0 for r in rows),
            'by_episode':{r['episode']:r.get('ate_full') for r in rows}}
    marker.write_text(json.dumps(result,indent=2)+'\n')
    log(f'complete {batch}/{exp} mean={result["mean_ate"]:.6f} peak={result["max_peak_fuel"]} sha={result["wasm_sha256"]}')
    return result

def main():
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True); make_pools()
    deadline=time.monotonic()+3600
    results={}
    # Screen candidates against the exact server-best artifact, then confirm only candidates
    # with >=0.015 m improvement and no catastrophic per-flight regressions (>0.3 m).
    for exp,da in EXPS:
        if time.monotonic()>deadline: log('60-minute eval budget reached before '+exp); return
        results[exp]=evalone(exp,build(exp,da),'screen')
    base=results['baseline']['by_episode']
    passed=[]
    for exp,_ in EXPS[1:]:
        rr=results[exp]; dif=[rr['by_episode'][k]-base[k] for k in base]
        if statistics.mean(dif)<-0.015 and max(dif)<0.30: passed.append(exp)
    (WORK/'screen_summary.json').write_text(json.dumps({'results':{k:{a:b for a,b in v.items() if a!='by_episode'} for k,v in results.items()},'passed':passed},indent=2)+'\n')
    log('screen passed: '+(','.join(passed) or 'none; queue complete'))
    if passed:
        evalone('baseline', BASE, 'confirm')
    for exp in passed:
        if time.monotonic()>deadline: log('60-minute eval budget reached before confirmation '+exp); return
        evalone(exp,build(exp,dict(EXPS)[exp]),'confirm')
    log('queue complete')
if __name__=='__main__': main()
