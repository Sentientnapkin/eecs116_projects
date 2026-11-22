"""Evaluate only named allowlisted pools; store all outputs under stlong."""
import argparse,concurrent.futures,hashlib,json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
H=Path(__file__).resolve().parent;SM=H.parent;ROOT=SM.parents[1];BASE=ROOT.parent
PY=BASE/'venv-viobench-9b1b079/bin/python';SRC=Path('/dev/shm/sebastian-vio/viobench')
POOLS={p:BASE/'tmp/st_pools'/p for p in ['st2dev','st2conf','st1dev','st1conf']};POOLS.update({p:BASE/'tmp/lv_pools'/p for p in ['st3','fdev','fconf']})
def suffix(rep):return '' if rep==0 else f'_r{rep}'
def baseline(pool,rep):
    tag='glNP'+suffix(rep);rows=json.load(open(SM/f'learnvel/tables/{tag}__{pool}.json'))
    reports=ROOT/f'research/results/single_model/lv_{tag}'/pool
    fuels=[]
    for p in reports.glob('*/*/report/logs/*/fuel.npy'): fuels.append(np.load(p))
    assert fuels
    return rows,np.concatenate(fuels)
def run(name,rep,pool,workers):
    assert pool in POOLS and workers<=48
    tag=name+suffix(rep); wasm=H/'builds'/tag/'solution.wasm';assert wasm.exists();digest=hashlib.sha256(wasm.read_bytes()).hexdigest()
    archives=sorted(POOLS[pool].glob('*.zip'));refs,_=baseline(pool,rep);lookup={r['ep']:r for r in refs};assert {z.stem for z in archives}==set(lookup)
    # Evaluate only already-validated baseline episodes; no other scene or archive is opened.
    if pool in ['fdev','fconf']:
        assert all(int(hashlib.sha256(f"{r['cat']}:{r['scene']}".encode()).hexdigest()[:8],16)%5 in ([0,1,2] if pool=='fdev' else [3]) for r in refs)
    out=H/'results'/tag/pool;out.mkdir(parents=True,exist_ok=True);shared=BASE/'tmp/stlong_eval_cache'/digest;shared.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,PYTHONPATH=str(SRC),VIOBENCH_PNG_CACHE='0',XDG_CACHE_HOME=str(shared),VIOBENCH_SHARED_CACHE=str(shared),VIOBENCH_COMPILE_LOCK=str(shared/'compile.lock'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TMPDIR=str(BASE/'tmp'),PYTHONDONTWRITEBYTECODE='1')
    with open(out/'warm.log','w') as f:subprocess.run([str(PY),'-B','-c','from pathlib import Path;import sys;from viobench.tools.runner.engine import Engine;Engine().module(Path(sys.argv[1]).read_bytes())',str(wasm)],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    def one(z):
        w=out/z.stem;w.mkdir(exist_ok=True);report=w/'report/report.json'
        if not report.exists():
            with open(w/'evaluate.log','w') as f:subprocess.run([str(PY),'-B',str(SM/'evalmain.py'),'evaluate',str(wasm),str(z.resolve())],cwd=w,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
            (w/'report-solution').rename(w/'report')
        d=json.load(open(report))['episodes'][0];assert d['completed'] and d['metrics']['filled_frames']==0
        return dict(ep=z.stem,scene=lookup[z.stem]['scene'],cat=lookup[z.stem]['cat'],ate_rmse=d['metrics']['ate_rmse'],peak=d['fuel_per_frame_max'],p99=d['fuel_per_frame_p99'],filled_frames=d['metrics']['filled_frames'],ok=d['completed'])
    rows=[];t=time.time()
    with concurrent.futures.ThreadPoolExecutor(workers) as ex:
        for i,r in enumerate(ex.map(one,archives),1):
            rows.append(r)
            if i%20==0: print(tag,pool,i,'/',len(archives),round(time.time()-t),'sec',flush=True)
    (H/f'tables/{tag}__{pool}.json').write_text(json.dumps(rows));print('DONE',tag,pool,'ATE',np.mean([r['ate_rmse'] for r in rows]),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--rep',type=int,default=0);p.add_argument('--pools',default='st2dev,st3');p.add_argument('--workers',type=int,default=48);a=p.parse_args()
    for pool in a.pools.split(','):run(a.name,a.rep,pool,a.workers)
