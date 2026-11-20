"""Crash-isolated generation of the immutable final roster on GPU 7.

Each child has an individual raw/log directory. The supervisor alone publishes
archives and status files, avoiding shared NFS append logs. Resume retries only
the same manifest flights and seeds; it never replaces a failed flight.
"""
import argparse,concurrent.futures,datetime,hashlib,json,os,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PYTHON='/data/backups/rganapa/Sebastian/venv-sim/bin/python'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=16);p.add_argument('--limit',type=int);p.add_argument('--passes',type=int,default=3);a=p.parse_args()
    if not 1<=a.workers<=32:raise ValueError('generation concurrency must be1..32')
    manifest=json.loads((HERE/'manifest.json').read_text());roster_path=HERE/'roster.json'
    if sha(roster_path)!=manifest['roster_sha256']:raise ValueError('Frozen roster checksum mismatch')
    if sha(HERE/'selected_config_median.json')!=manifest['config_sha256']:raise ValueError('Frozen rule checksum mismatch')
    flights=json.loads(roster_path.read_text())['flights'];raw=Path(manifest['raw_root']);raw.mkdir(parents=True,exist_ok=True)
    for part in ['bench','work','status','locks']: (raw/part).mkdir(exist_ok=True)
    env=os.environ.copy();base=Path('/data/backups/rganapa/Sebastian/gen')
    env.update(CUDA_VISIBLE_DEVICES='7',CUDAARCHS='90',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',TMPDIR='/data/backups/rganapa/Sebastian/tmp',VIOBENCH_CACHE='/dev/shm/sebastian-gen/shared-viobench',HYPERLUX_CACHE_DIR='/dev/shm/sebastian-gen/shared-hyperlux',CONTA_CACHE=str(base/'conta'),VIOBENCH_SPOOL=str(base/'spool'),XDG_CACHE_HOME=str(base/'xdg'),HF_HOME='/data/backups/rganapa/Sebastian/hf')
    env['PATH']='/usr/local/cuda/bin:/data/backups/rganapa/Sebastian/venv-sim/bin:'+env.get('PATH','/usr/bin:/bin')
    def one(f):
        import fcntl
        name=f['id'];target=raw/'bench'/f'{name}.zip';status=raw/'status'/f'{name}.json'
        with (raw/'locks'/f'{name}.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if target.exists():return {'id':name,'status':'cached'}
            job=raw/'work'/name;job.mkdir(parents=True,exist_ok=True);started=time.monotonic()
            cmd=[PYTHON,str(ROOT/'research/native_campaign.py'),'generate','--gen-roster',str(roster_path),'--gen-raw',str(job),'--ids',name,'--workers','1','--worker','0','--min-free-gb','200']
            with (job/'generate.log').open('a') as log:
                log.write('\nATTEMPT '+datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n');log.flush()
                child=subprocess.run(cmd,cwd=ROOT/'research',env=env,stdout=log,stderr=subprocess.STDOUT,check=False)
            archive=job/'bench'/target.name;meta=archive.with_suffix('.json');success=archive.exists() and meta.exists()
            event={'id':name,'seed':f['seed'],'returncode':child.returncode,'seconds':round(time.monotonic()-started,2),'status':'ok' if success else 'failed','log':str(job/'generate.log'),'time':datetime.datetime.now(datetime.timezone.utc).isoformat()}
            if success:
                record=json.loads(meta.read_text())
                if record['sha256']!=sha(archive):raise ValueError(f'{name}: archive checksum mismatch')
                os.replace(meta,target.with_suffix('.json'));os.replace(archive,target)
                event['archive_sha256']=record['sha256'];event['bytes']=record['bytes']
            temporary=status.with_suffix('.tmp');temporary.write_text(json.dumps(event,indent=2)+'\n');temporary.replace(status)
            return event
    start=time.monotonic();finished=0
    for attempt in range(1,a.passes+1):
        pending=[f for f in flights if not (raw/'bench'/f"{f['id']}.zip").exists()]
        if a.limit is not None:pending=pending[:a.limit]
        print(f'pass={attempt} pending={len(pending)} workers={a.workers} gpu=7 manifest={sha(HERE/"manifest.json")}',flush=True)
        if not pending:break
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
            futures={pool.submit(one,f):f for f in pending}
            for future in concurrent.futures.as_completed(futures):
                f=futures[future]
                try:event=future.result()
                except Exception as error:event={'id':f['id'],'status':'supervisor_error','error':repr(error)}
                finished+=1;done=sum((raw/'bench'/f"{f['id']}.zip").exists() for f in flights)
                event.update(completed_archives=done,total=192,wall_seconds=round(time.monotonic()-start,1));print(json.dumps(event),flush=True)
                progress={'manifest_sha256':sha(HERE/'manifest.json'),'workers':a.workers,'gpu':7,'completed_archives':done,'total':len(flights),'wall_seconds':round(time.monotonic()-start,1),'last_event':event}
                temp=raw/'progress.tmp';temp.write_text(json.dumps(progress,indent=2)+'\n');temp.replace(raw/'progress.json')
        if a.limit is not None:break
    done=sum((raw/'bench'/f"{f['id']}.zip").exists() for f in flights)
    print(json.dumps({'complete':done==192,'completed_archives':done,'total':192,'wall_seconds':round(time.monotonic()-start,1)}),flush=True)
if __name__=='__main__':main()
