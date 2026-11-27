"""Small causal geometry capacity screen; isolated copies, never edits baseline.
Not a full bundle-adjustment benchmark or a held-out result.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
G = REPO.parent/'gen3'
WORK = Path('/tmp/vio-research-20261126/geometry')
WORK.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(REPO))
from research.single_model.run_variant import run_guest_fast

ref=json.loads((G/'evals/sw_a1_Ze0__v3val.json').read_text())
# Fixed deterministic scene/start-stratified sample, independent of error ranking.
chosen=[]
for c in ['room','warehouse','forest']:
    for st in ['hover','mid-flight']:
        group=sorted((r for r in ref if r['setting_class']==c and r['start']==st),key=lambda r:hashlib.sha256(r['id'].encode()).hexdigest())
        chosen.extend(group[:3])
pool=WORK/'panel18';pool.mkdir(exist_ok=True)
for r in chosen:
    dst=pool/(r['id']+'.zip')
    if not dst.exists():dst.symlink_to((G/'pools/v3val'/dst.name).resolve())
(WORK/'panel.json').write_text(json.dumps(chosen,indent=2))
base='PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0'
variants={
    'control':base,
    'budget_control':base+' GOV_B=100e6',
    'features2x':base+' GRID_X=20 GRID_Y=6 GOV_B=100e6',
    'geometry5x':base.replace('ITER_UPD=1','ITER_UPD=3')+' GRID_X=20 GRID_Y=15 MAX_CLONES=12 MAX_OBS=14 GOV_B=100e6',
    'geometry5x_no_net':base.replace('ITER_UPD=1','ITER_UPD=3')+' GRID_X=20 GRID_Y=15 MAX_CLONES=12 MAX_OBS=14 GOV_B=100e6 LC_ENABLE=0',
    'geometry10x':base.replace('ITER_UPD=1','ITER_UPD=3')+' GRID_X=30 GRID_Y=20 MAX_CLONES=12 MAX_OBS=14 MAX_UPDATE_FEATURES=200 GOV_B=1e9',
}
allrows={}
for name,defs in variants.items():
    p=WORK/name;src=p/'src';src.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(G/'research/baseline/baseA160.c',src/'solution.c')
    shutil.copyfile(REPO/'research/single_model/linejac/CMakeLists.txt',src/'CMakeLists.txt')
    wasm=p/'solution.wasm'
    if not wasm.exists():
        cmd=['cmake','-S',str(src),'-B',str(src/'build'),'-DCMAKE_TOOLCHAIN_FILE=/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk/share/cmake/wasi-sdk-p1.cmake','-DVIOBENCH_NATIVE_DIR=/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native','-DCMAKE_C_FLAGS='+' '.join('-D'+d for d in defs.split())]
        with (p/'build.log').open('w') as log:
            subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
            subprocess.run(['cmake','--build',str(src/'build')],stdout=log,stderr=subprocess.STDOUT,check=True)
        shutil.copyfile(src/'build/solution.wasm',wasm)
    sha=hashlib.sha256(wasm.read_bytes()).hexdigest()
    if name=='control':assert sha=='670bc1da4bab33445d59138a4ec04a5c354d892dbce8db6a8a8cd59f00c562cd',sha
    (p/'manifest.json').write_text(json.dumps(dict(flags=defs,sha256=sha,bytes=wasm.stat().st_size),indent=2))
    result=run_guest_fast(wasm,pool,p/'eval',workers=4,name=name)
    allrows[name]=json.loads(result.read_text())
    (WORK/'results.json').write_text(json.dumps(allrows,indent=1))
    print('DONE',name,sha,flush=True)
