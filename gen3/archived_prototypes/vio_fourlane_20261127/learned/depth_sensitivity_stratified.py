#!/usr/bin/env python3
"""Bounded old-Ze0 GT-pose-triangulated pseudo-depth sensitivity. 24 fixed episodes; no training."""
import sys, os, json, hashlib, subprocess, shutil, statistics, time
from pathlib import Path
ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects'); GEN=ROOT.parent/'gen3'; I3=GEN/'research/i3'
WORK=Path('/tmp/vio_fourlane_20261127/learned/stratified'); OUT=Path('/dev/shm/vio_fourlane_20261127/learned/stratified')
TC=ROOT.parent/'tmp/viobench-toolchain'; NAT=Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
CM=ROOT/'research/single_model/linejac/CMakeLists.txt'; BASE='PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 OR=1'
SRC=I3/'src_or.c'; POOL=I3/'pools/i3s120'; VENV=ROOT.parent/'venv-teacher/bin/python'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(key, extra):
    if key=='baseline': return GEN/'scratch_up/gslv_s3_A160ft_Ze0.wasm'
    target=OUT/'builds'/key/'solution.wasm'; target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): return target
    src=OUT/'builds'/key/'src'; src.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SRC,src/'solution.c'); shutil.copy2(CM,src/'CMakeLists.txt')
    hook = '' if key=='orcontrol' else ' OR_DEP_ON=1'
    flags=' '.join('-D'+x for x in (BASE+' '+extra+hook).split())
    b=src/'build'
    cmds=[['cmake','-S',str(src),'-B',str(b),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={flags}'],['cmake','--build',str(b),'-j2']]
    for c in cmds:
        p=subprocess.run(c,capture_output=True,text=True)
        if p.returncode: raise RuntimeError((p.stdout+p.stderr)[-3000:])
    shutil.copy2(b/'solution.wasm',target); return target
def main():
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    batch=OUT/'pool24'; batch.mkdir(exist_ok=True)
    buckets={}
    for f in sorted(POOL.glob('*.zip')):
        meta=GEN/'out/up'/(f.stem+'.json')
        if not meta.exists(): continue
        m=json.loads(meta.read_text()); scene=str(m.get('setting_class','')).lower(); start=str(m.get('start','')).lower()
        if scene in ('room','warehouse','forest'):
            buckets.setdefault((scene,'hover' if 'hover' in start else 'mid'),[]).append(f)
    files=[]
    for key in sorted(buckets):
        if len(buckets[key])<4: raise RuntimeError(f'insufficient stratum {key}')
        files.extend(buckets[key][:4])
    if len(files)!=24: raise RuntimeError('expected 24 balanced episodes')
    for f in files:
        q=batch/f.name
        if not q.exists(): q.symlink_to(f)
    exps=[('baseline',None),('orcontrol',''),('independent10','OR_DEP=0.1'),('independent20','OR_DEP=0.2'),('shared10','OR_SCALE=0.1'),('shared20','OR_SCALE=0.2'),('sharedcov10','OR_DEP=0.1 OR_NT=2'),('sharedcov20','OR_DEP=0.2 OR_NT=2')]
    manifest={'source_sha256':sha(SRC),'old_zpe_reference':str(GEN/'scratch_up/gslv_s3_A160ft_Ze0.wasm'),'pool_episodes':[p.name for p in files], 'n':24,'strata':'4 episodes each in room/warehouse/forest x hover/mid-flight',
      'depth_semantics':'independent zero-mean Gaussian fractional noise on GT-pose triangulated feature depth; OR_DEP_ON hook, not renderer depth or exact correspondences',
      'sigma_fraction':[0.1,0.2], 'covariance':'independent per landmark or one shared episode-scale Gaussian OR_SCALE; distinct controls', 'experiments':exps,'deadline_seconds':3600,'workers':4}
    (WORK/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    sys.path.insert(0,str(ROOT)); from research.single_model.run_variant import run_guest_fast
    deadline=time.monotonic()+3600
    for name,extra in exps:
        if time.monotonic()>=deadline: raise TimeoutError('global 60-minute queue budget reached')
        marker=WORK/(name+'.done.json')
        if marker.exists(): continue
        wasm=build(name,extra)
        if time.monotonic()>=deadline: raise TimeoutError('global 60-minute queue budget reached before eval')
        score=run_guest_fast(wasm,batch,OUT/'evals'/name,workers=4,name='learned_depth_'+name)
        rows=json.loads(Path(score).read_text())['rows']; vals=[r['ate_full'] for r in rows if r.get('ate_full') is not None]
        if len(vals)!=24: raise RuntimeError(f'{name} incomplete {len(vals)}/24')
        result={'name':name,'n':24,'mean_ate':statistics.mean(vals),'median_ate':statistics.median(vals),'max_peak_fuel':max(r.get('peak_fuel_per_frame',0) or 0 for r in rows),'wasm_sha256':sha(wasm),'episode_ate':{r['episode']:r.get('ate_full') for r in rows}}
        marker.write_text(json.dumps(result,indent=2)+'\n')
        with (WORK/'results.tsv').open('a') as f: f.write(f"{name}\t24\t{result['mean_ate']:.6f}\t{result['median_ate']:.6f}\t{result['max_peak_fuel']}\t{result['wasm_sha256']}\n")
    (WORK/'queue.done').write_text('all 6 stratified 24-episode evaluations completed\n')
if __name__=='__main__': main()
