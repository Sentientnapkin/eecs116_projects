"""Direct Wasmtime replay with optional job-fuel diagnostics. No held-out pools.

Examples: python -m ...ensemble2.replay BUILD st2dev --limit 12 --workers 8
The standard engine and Sandbox enforce the actual ABI/fuel accounting.
"""
import argparse,hashlib,json,os,sys,traceback
from multiprocessing import Pool
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=['/dev/shm/sebastian-vio/viobench',str(ROOT/'research/single_model')]
POOLS={k:Path('/data/backups/rganapa/Sebastian/tmp/st_pools')/k for k in ('st2dev','st2conf','st1dev','st1conf')}
POOLS.update({k:Path('/data/backups/rganapa/Sebastian/tmp/lv_pools')/k for k in ('st3','fconf','fdev')})
STATE={}

def one(args):
    wasm,out,archive,profile=args
    name=Path(archive).stem;target=Path(out)/(name+'.npz')
    if target.exists():return name,'cached'
    try:
        import wasmtime,png_cache
        png_cache.install()
        from viobench.tools.runner import sandbox as S
        from viobench.tools.runner.engine import Engine
        from viobench.tools.datasets.sources import episodes
        state=STATE
        if not state.get('patched'):
            state['patched']=True
            orig=S.Sandbox._arm
            def arm(self,fuel,wall):
                state['store']=self.store;state['fuel0']=fuel;orig(self,fuel,wall)
            S.Sandbox._arm=arm
            orig_define=wasmtime.Linker.define_wasi
            def define(self):
                orig_define(self)
                def mark(j,a,b,c):
                    now=state['fuel0']-state['store'].get_fuel();frame=state['frame']
                    if j==80:state['primary']=(now,a)
                    elif j==81:state['lag']=(a,b,c)
                    elif j==90:state['stage']=(a,b,now)
                    elif j==91:
                        ph,need,start=state['stage'];state['stages'].append((frame,ph,need,now-start))
                    elif j>0:state['stack'].append((j,a,b,c,now,len(state['stack'])))
                    else:
                        jj,aa,bb,cc,start,depth=state['stack'].pop()
                        assert jj==-j,(jj,j)
                        state['jobs'].append((frame,jj//1000,jj%1000,a,b,c,now-start,depth))
                self.define_func('env','ens_mark',wasmtime.FuncType([wasmtime.ValType.i32()]*4,[]),mark)
            wasmtime.Linker.define_wasi=define
        ep=next(episodes([str(archive)]));gt=ep.ground_truth_state()[:,:3]
        sb=S.Sandbox(str(wasm),Engine(),limits=S.Limits(),log_dir=str(Path(out)/('logs_'+name)))
        cfg,frames=ep.adapt(sb.resolution);sb.init(cfg)
        poses=[];fuel=[];primary=[];lag=[];states=[];state.update(jobs=[],stages=[],stack=[],frame=0)
        for idx,(t,frame,imu) in enumerate(ep.steps(frames)):
            state.update(frame=idx,primary=(0,0),lag=(0,0,0))
            res=sb.step(t,frame,imu)
            poses.append(np.r_[res.pose,res.twist]);fuel.append(res.fuel)
            primary.append(state['primary']);lag.append(state['lag'])
            if 'ens_states' in sb.instance.exports(sb.store):
                ptr=sb.instance.exports(sb.store)['ens_states'](sb.store)
                states.append(np.frombuffer(sb.memory.read(sb.store,ptr,ptr+208),dtype='<f8').copy())
        pose=np.asarray(poses);n=min(len(pose),len(gt))
        ate=float(np.sqrt(np.mean(np.sum((pose[:n,:3]-gt[:n])**2,axis=1))))
        stats=[]
        if 'ens_stats' in sb.instance.exports(sb.store):
            ptr=sb.instance.exports(sb.store)['ens_stats'](sb.store)
            stats=np.frombuffer(sb.memory.read(sb.store,ptr,ptr+48),dtype='<i4').copy()
        np.savez(target,pose=pose,gt=gt,fuel=np.array(fuel),primary=np.array(primary),lag=np.array(lag),
                 jobs=np.array(state['jobs'],dtype=np.int64).reshape(-1,8),stages=np.array(state['stages'],dtype=np.int64).reshape(-1,4),
                 stats=np.array(stats),ate=ate,states=np.array(states))
        return name,dict(ate=ate,peak=max(fuel),frames=n,stats=list(map(int,stats)))
    except Exception:
        error=traceback.format_exc();(Path(out)/(name+'.error')).write_text(error);return name,dict(error=error[-1600:])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('build');ap.add_argument('pool',choices=POOLS);ap.add_argument('--limit',type=int);ap.add_argument('--workers',type=int,default=24);ap.add_argument('--wasm',type=Path);a=ap.parse_args()
    os.environ.update(TMPDIR='/data/backups/rganapa/Sebastian/tmp/ensemble2',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VIOBENCH_PNG_CACHE='1')
    wasm=a.wasm or HERE/'build'/a.build/'solution.wasm'
    digest=hashlib.sha256(wasm.read_bytes()).hexdigest();out=HERE/'replays'/a.build/a.pool
    out.mkdir(parents=True,exist_ok=True)
    manifest=out/'manifest.json';meta=dict(wasm=str(wasm),sha256=digest,pool=str(POOLS[a.pool]))
    if manifest.exists():assert json.loads(manifest.read_text())==meta,'Build changed: use a new run name'
    manifest.write_text(json.dumps(meta,indent=2)+'\n')
    archives=sorted(POOLS[a.pool].glob('*.zip'))
    if a.limit:archives=archives[::max(1,len(archives)//a.limit)][:a.limit]
    assert archives,POOLS[a.pool]
    results=[]
    with Pool(a.workers) as p:
        for name,result in p.imap_unordered(one,[(str(wasm),str(out),str(z),True) for z in archives]):
            results.append((name,result));print(name,json.dumps(result),flush=True)
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    if any(isinstance(r,dict) and 'error'in r for _,r in results):raise SystemExit(1)

if __name__=='__main__':main()
