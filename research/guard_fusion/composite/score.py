"""Consolidate saved composite runs; missing runs count at origin, never disappear."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
from ..evaluate import summary
from ..traj import DEFAULT_RAW, load_truth


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def consolidate(scores_path, raw=DEFAULT_RAW, offline=None, config=None):
    data=json.loads(Path(scores_path).read_text())
    archives=data['guest']['archives']
    expected=[Path(p).stem for p in archives]
    lookup={r['episode']:r for r in data['rows']}
    def one(name):
        row=dict(lookup.get(name,{'episode':name,'error':'missing result row'}))
        if row.get('ate_full') is None or not np.isfinite(row['ate_full']):
            times,truth,_=load_truth(raw,name)
            row.update(ate_full=float(np.sqrt(np.mean(np.sum(truth[:,:3]**2,axis=1)))),
                       frames=len(times),filled_full=len(times),completed=False,
                       failure=row.get('failure') or row.get('error') or 'missing finite ATE',
                       origin_substitution=True)
        else:
            row['origin_substitution']=False
        return row
    with ThreadPoolExecutor(16) as pool:
        rows=list(pool.map(one,expected))
    report={'metric':'mean_unaligned_ate_m','status':'experimental; full release preflight and G1 required',
        'guest':data['guest'],'source_scores':str(Path(scores_path).resolve()),
        'source_scores_sha256':sha(scores_path),'summary':summary([r['ate_full'] for r in rows]),
        'origin_substitutions':sum(r['origin_substitution'] for r in rows),
        'completed_flights':sum(bool(r.get('completed')) for r in rows),
        'zero_filled_flights':sum(r.get('filled_full')==0 for r in rows),
        'peak_fuel_per_frame':max((r.get('peak_fuel_per_frame',0) or 0 for r in rows),default=None),
        'rows':rows}
    if offline is not None:
        declared=json.loads(Path(offline).read_text())
        arm=json.loads(Path(config).read_text())['arm'] if config else declared['deployment_candidate']['arm']
        key=arm['name']; offrows={r['episode']:r for r in declared['rows']}
        if set(offrows)!=set(expected):
            raise ValueError('Offline and runtime flight sets differ')
        off=np.array([offrows[r['episode']]['scores'][key] for r in rows])
        actual=np.array([r['ate_full'] for r in rows])
        report['offline_comparison']={'arm':arm,'same_rule':True,
            'caveat':'full runtime uses a new OpenCV4.12 N2 backend; saved offline sources used frozen guests',
            'offline_mean':float(off.mean()),'runtime_mean':float(actual.mean()),
            'mean_ratio':float(actual.mean()/off.mean()),
            'within_5pct_mean':bool(abs(actual.mean()/off.mean()-1)<=.05),
            'mean_paired_delta_m':float(np.mean(actual-off)),
            'median_paired_delta_m':float(np.median(actual-off))}
        for i,row in enumerate(rows):
            row['offline_ate_full']=float(off[i])
            row['runtime_minus_offline_m']=float(actual[i]-off[i])
    return report


def run_guest(wasm, episodes, out, workers=48, name='guard_safe', limit=None, cache=None):
    """Run pinned evaluator processes with one shared module cache/compile lock."""
    from ... import wasm_eval
    wasm=Path(wasm).resolve()
    source=Path(episodes).resolve()
    archives=sorted(source.glob('*.zip')) if source.is_dir() else [source]
    if limit is not None:
        archives=archives[:limit]
    if not archives:
        raise ValueError('No episode archives')
    digest=sha(wasm)
    base=Path(out).resolve(); base.mkdir(parents=True,exist_ok=True)
    folder=base/(name+'-'+digest[:8]); folder.mkdir(parents=True,exist_ok=True)
    shared=Path(cache or os.environ.get('VIOBENCH_SHARED_CACHE', '/dev/shm/sebastian-vio/guard-cache/'+digest)).resolve()
    shared.mkdir(parents=True,exist_ok=True)
    lock=Path(os.environ.get('VIOBENCH_COMPILE_LOCK',str(shared/'compile.lock'))).resolve()
    lock.parent.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env.update(PYTHONPATH=str(wasm_eval.SRC),XDG_CACHE_HOME=str(shared),
        VIOBENCH_COMPILE_LOCK=str(lock),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    guest={'name':name,'wasm':str(wasm),'sha256':digest,'archives':list(map(str,archives)),
        'evaluator_src':str(wasm_eval.SRC),'shared_cache':str(shared),'compile_lock':str(lock)}
    (folder/'guest.json').write_text(json.dumps(guest,indent=2)+'\n')
    # Warm a single cache entry before scheduling many episode processes. The
    # upstream engine's compilation lock covers cache lookup plus compilation.
    todo=[a for a in archives if not (folder/a.stem/'report/report.json').exists()]
    if todo:
        print(f'Warming shared module cache for {digest[:12]}: {shared}',flush=True)
        with (folder/'cache-warm.log').open('w') as log:
            subprocess.run([sys.executable,'-c',
                'from pathlib import Path; import sys; from viobench.tools.runner.engine import Engine; Engine().module(Path(sys.argv[1]).read_bytes())',
                str(wasm)],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    def one(archive):
        import fcntl
        work=folder/archive.stem; work.mkdir(parents=True,exist_ok=True)
        with (work/'run.lock').open('a') as episode_lock:
            fcntl.flock(episode_lock,fcntl.LOCK_EX)
            report=work/'report/report.json'
            if not report.exists():
                with (work/'evaluate.log').open('w') as log:
                    subprocess.run([sys.executable,'-B','-m','viobench','evaluate',str(wasm),str(archive),
                        '-o',str(work/'report')],cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,check=False)
            return wasm_eval.score_one(archive,work)
    started=time.monotonic(); lookup={}
    print(f'{len(archives)} episodes, {len(archives)-len(todo)} cached, workers={min(workers,64)}',flush=True)
    with ThreadPoolExecutor(min(workers,64)) as pool:
        future_to_archive={pool.submit(one,a):a for a in archives}
        for i,future in enumerate(as_completed(future_to_archive),1):
            archive=future_to_archive[future]
            try:
                row=future.result()
            except Exception as exc:
                row={'episode':archive.stem,'error':f'{type(exc).__name__}: {exc}'}
            lookup[archive.stem]=row
            if i%10==0 or i==len(archives):
                print(f'{i}/{len(archives)} finished, {time.monotonic()-started:.1f}s',flush=True)
            # Atomic progress snapshot; useful after interruption. A missing row
            # remains explicit and will be run on the next invocation.
            snapshot={'guest':guest,'rows':[lookup.get(a.stem,{'episode':a.stem,'error':'pending'}) for a in archives]}
            temporary=folder/'scores.partial.json'
            temporary.write_text(json.dumps(snapshot,indent=1)+'\n')
            temporary.replace(folder/'scores.json')
    return folder/'scores.json'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scores',type=Path)
    p.add_argument('--wasm',type=Path)
    p.add_argument('--episodes',type=Path)
    p.add_argument('--workers',type=int,default=48)
    p.add_argument('--name',default='guard_safe')
    p.add_argument('--limit',type=int)
    p.add_argument('--cache',type=Path)
    p.add_argument('--raw',type=Path,default=DEFAULT_RAW)
    p.add_argument('--offline',type=Path)
    p.add_argument('--config',type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args()
    if a.wasm:
        if not a.episodes:
            p.error('--wasm requires --episodes')
        score_path=run_guest(a.wasm,a.episodes,a.out,a.workers,a.name,a.limit,a.cache)
        report=consolidate(score_path,a.episodes if a.episodes.is_dir() else a.episodes.parent,a.offline,a.config)
        a.out=score_path.parent/'summary.json'
    else:
        if not a.scores:
            p.error('provide --scores or --wasm with --episodes')
        report=consolidate(a.scores,a.raw,a.offline,a.config)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','guest')},indent=2))

if __name__=='__main__':
    main()
