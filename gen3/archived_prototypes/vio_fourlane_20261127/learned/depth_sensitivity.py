#!/usr/bin/env python3
"""Bounded old-Ze0 GT-pose-triangulated pseudo-depth sensitivity. 24 fixed episodes; no training."""
import sys, os, json, hashlib, subprocess, shutil, statistics, time
from pathlib import Path
ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects'); GEN=ROOT.parent/'gen3'; I3=GEN/'research/i3'
WORK=Path('/tmp/vio_fourlane_20261127/learned'); OUT=Path('/dev/shm/vio_fourlane_20261127/learned')
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
    flags=' '.join('-D'+x for x in (BASE+' '+extra+' OR_DEP_ON=1').split())
    b=src/'build'
    cmds=[['cmake','-S',str(src),'-B',str(b),f'-DCMAKE_TOOLCHAIN_FILE={TC}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',f'-DVIOBENCH_NATIVE_DIR={NAT}',f'-DCMAKE_C_FLAGS={flags}'],['cmake','--build',str(b),'-j2']]
    for c in cmds:
        p=subprocess.run(c,capture_output=True,text=True)
        if p.returncode: raise RuntimeError((p.stdout+p.stderr)[-3000:])
    shutil.copy2(b/'solution.wasm',target); return target
def main():
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    batch=OUT/'pool24'; batch.mkdir(exist_ok=True)
    files=sorted(POOL.glob('*.zip'))[:24]
    if len(files)!=24: raise RuntimeError('expected >=24 pool episodes')
    for f in files:
        q=batch/f.name
        if not q.exists(): q.symlink_to(f)
    exps=[('baseline',None),('sd02','OR_DEP=0.02'),('sd05','OR_DEP=0.05'),('sd10','OR_DEP=0.1')]
    manifest={'source_sha256':sha(SRC),'old_zpe_reference':str(GEN/'scratch_up/gslv_s3_A160ft_Ze0.wasm'),'pool_episodes':[p.name for p in files], 'n':24,
      'depth_semantics':'independent zero-mean Gaussian fractional noise on GT-pose triangulated feature depth; OR_DEP_ON hook, not renderer depth or exact correspondences',
      'sigma_fraction':[0.02,0.05,0.1], 'covariance':'independent per landmark; no shared frame/episode scale term in this first sensitivity screen', 'experiments':exps,'deadline_seconds':3600,'workers':4}
    (WORK/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    sys.path.insert(0,str(ROOT)); from research.single_model.run_variant import run_guest_fast
    for name,extra in exps:
        marker=WORK/(name+'.done.json')
        if marker.exists(): continue
        wasm=build(name,extra)
        score=run_guest_fast(wasm,batch,OUT/'evals'/name,workers=4,name='learned_depth_'+name)
        rows=json.loads(Path(score).read_text())['rows']; vals=[r['ate_full'] for r in rows if r.get('ate_full') is not None]
        if len(vals)!=24: raise RuntimeError(f'{name} incomplete {len(vals)}/24')
        result={'name':name,'n':24,'mean_ate':statistics.mean(vals),'median_ate':statistics.median(vals),'max_peak_fuel':max(r.get('peak_fuel_per_frame',0) or 0 for r in rows),'wasm_sha256':sha(wasm),'episode_ate':{r['episode']:r.get('ate_full') for r in rows}}
        marker.write_text(json.dumps(result,indent=2)+'\n')
        with (WORK/'results.tsv').open('a') as f: f.write(f"{name}\t24\t{result['mean_ate']:.6f}\t{result['median_ate']:.6f}\t{result['max_peak_fuel']}\t{result['wasm_sha256']}\n")
    (WORK/'queue.done').write_text('all 4 matched 24-episode evaluations completed\n')
if __name__=='__main__': main()
