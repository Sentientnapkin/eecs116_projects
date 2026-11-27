#!/usr/bin/env python3
"""Bounded, resumable low-fuel screen: shrink the active clone window geometrically."""
import json, hashlib, os, shutil, statistics, subprocess, sys, time
from pathlib import Path
ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects')
GEN=ROOT.parent/'gen3'
BASE=GEN/'scratch_up/gslv_s3_snace6e1.wasm'
SRC=GEN/'agents/anchors/base_sn.c'
CM=ROOT/'research/single_model/linejac/CMakeLists.txt'
TC=ROOT.parent/'tmp/viobench-toolchain'
NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
POOL=GEN/'agents/anchors/pools/v3val'
WORK=Path('/tmp/vio_fourlane_20261127/extreme')
OUT=Path('/dev/shm/vio_fourlane_20261127/extreme')
SUB=OUT/'pools'
ACCURACY=Path('/tmp/vio_fourlane_20261127/accuracy')
BASE_MARK=ACCURACY/'screen_baseline.done.json'
FLAGS=('PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 '
       'INV_VZ=0 EDGE=0 SN=1 NS_GCOST=1 AN_ACE=1 AN_DTH=4.0 AN_CEF=6 EDGE=1 EDGE_MYTH=10.0')
EXPS=[('mc5','MAX_CLONES=5 MAX_OBS=7'),('mc4','MAX_CLONES=4 MAX_OBS=6')]
BUDGET=3600

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def log(s):
    with (WORK/'worker.log').open('a') as f:
        f.write(time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime())+' '+s+'\n'); f.flush()
def wait_load():
    while float(Path('/proc/loadavg').read_text().split()[0])>170:
        log('loadavg > 170; pausing'); time.sleep(60)
def make_pools():
    SUB.mkdir(parents=True,exist_ok=True)
    for batch,ix in [('screen',0),('confirm',3)]:
        d=SUB/batch; d.mkdir(parents=True,exist_ok=True)
        for stale in d.glob('*.zip'):
            if stale.is_symlink(): stale.unlink()
        buckets={}
        for p in sorted(POOL.glob('*.zip')):
            meta=GEN/'out/up'/(p.stem+'.json')
            if not meta.exists(): continue
            m=json.loads(meta.read_text()); scene=str(m.get('setting_class','')).lower(); start=str(m.get('start','')).lower()
            if scene not in ('room','warehouse','forest'): continue
            key=(scene,'hover' if 'hover' in start else 'mid')
            buckets.setdefault(key,[]).append(p)
        for key,arr in buckets.items():
            if len(arr)<ix+3: raise RuntimeError(f'not enough flights in {key}')
            for p in arr[ix:ix+3]: (d/p.name).symlink_to(p)
        if len(list(d.glob('*.zip')))!=18: raise RuntimeError(f'{batch} panel is not 18 flights')
def build(name,extra):
    target=OUT/'builds'/name/'solution.wasm'; target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): return target
    sd=OUT/'builds'/name/'src'; sd.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SRC,sd/'solution.c'); shutil.copy2(CM,sd/'CMakeLists.txt')
    defs=' '.join('-D'+x for x in (FLAGS+' '+extra).split())
    b=sd/'build'
    r=subprocess.run(['cmake','-S',str(sd),'-B',str(b),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={defs}'],capture_output=True,text=True)
    if r.returncode: raise RuntimeError('cmake configure failed: '+r.stdout[-500:]+r.stderr[-500:])
    r=subprocess.run(['cmake','--build',str(b),'-j2'],capture_output=True,text=True)
    if r.returncode: raise RuntimeError('cmake build failed: '+r.stdout[-500:]+r.stderr[-500:])
    shutil.copy2(b/'solution.wasm',target); return target
def eval_one(name,wasm,batch):
    marker=WORK/f'{batch}_{name}.done.json'
    if marker.exists(): return json.loads(marker.read_text())
    wait_load(); sys.path.insert(0,str(ROOT))
    from research.single_model.run_variant import run_guest_fast
    score=run_guest_fast(wasm,SUB/batch,OUT/'evals'/batch,workers=4,name=f'extreme_{batch}_{name}')
    rows=json.loads(Path(score).read_text())['rows']; vals=[r['ate_full'] for r in rows if r.get('ate_full') is not None]
    if len(vals)!=18: raise RuntimeError(f'incomplete panel {batch}/{name}: {len(vals)}/18')
    r={'name':name,'batch':batch,'sha256':sha(wasm),'n':len(vals),'ate_raw':statistics.mean(vals),'median':statistics.median(vals),'peak_fuel':max((x.get('peak_fuel_per_frame',0) or 0) for x in rows),'by_episode':{x['episode']:x.get('ate_full') for x in rows}}
    marker.write_text(json.dumps(r,indent=2)+'\n')
    with (WORK/'results.tsv').open('a') as f: f.write(f"{name}\t{r['sha256']}\t{batch}\t18\t{r['ate_raw']:.6f}\t{r['peak_fuel']}\t\tcomplete\n")
    log(f"complete {batch}/{name}: ATE={r['ate_raw']:.6f} peak={r['peak_fuel']} sha={r['sha256']}")
    return r
def main():
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True); make_pools()
    deadline=time.monotonic()+BUDGET
    manifest={'baseline_sha256':sha(BASE),'source_sha256':sha(SRC),'flags':FLAGS,'experiments':EXPS,'screen':[p.name for p in sorted((SUB/'screen').glob('*.zip'))],'confirm':[p.name for p in sorted((SUB/'confirm').glob('*.zip'))],'workers':4,'cpu_seconds_cap':BUDGET,'test_holdout_hidden_upload':False}
    mp=WORK/'manifest.json'
    if mp.exists() and json.loads(mp.read_text())!=json.loads(json.dumps(manifest)): raise RuntimeError('manifest mismatch; refusing mixed resume')
    mp.write_text(json.dumps(manifest,indent=2)+'\n')
    # Accuracy lane is already measuring this exact current baseline and first 18-flight panel.
    while not BASE_MARK.exists():
        if time.monotonic()>deadline: log('budget reached waiting for paired baseline control'); return
        log('waiting for accuracy lane baseline marker'); time.sleep(15)
    base=json.loads(BASE_MARK.read_text())
    (WORK/'screen_baseline.done.json').write_text(json.dumps(base,indent=2)+'\n')
    base_ate=base['mean_ate']; base_peak=base['max_peak_fuel']
    cand=[]
    for name,extra in EXPS:
        if time.monotonic()>deadline: log('60 CPU-minute wall cap reached before '+name); return
        cand.append((name,eval_one(name,build(name,extra),'screen')))
    passed=[]
    for name,r in cand:
        paired=[r['by_episode'][k]-base['by_episode'][k] for k in base['by_episode']]
        # Keep only materially cheaper settings whose local accuracy loss is still limited.
        if r['peak_fuel']<=0.8*base_peak and statistics.mean(paired)<=0.10 and max(paired)<=0.45: passed.append(name)
    (WORK/'screen_summary.json').write_text(json.dumps({'baseline_ate':base_ate,'baseline_peak':base_peak,'passed':passed,'experiments':[{k:v for k,v in r.items() if k!='by_episode'} for _,r in cand]},indent=2)+'\n')
    log('screen gates passed: '+(','.join(passed) or 'none'))
    for name in passed:
        if time.monotonic()>deadline: log('60 CPU-minute cap reached before confirmation '+name); return
        extra=dict(EXPS)[name]; eval_one(name,build(name,extra),'confirm')
    log('queue complete')
if __name__=='__main__': main()
