import os, subprocess, time, pathlib, json
base=pathlib.Path('/tmp/vio_loop3/context_replication')
root=pathlib.Path('/dev/shm/vio_research_loop/reviews/cycle1_seed3')
root.mkdir(parents=True,exist_ok=True)
py='/data/backups/rganapa/Sebastian/venv-teacher/bin/python'
for k in (2,5):
    out=root/f'ctx{k}'; out.mkdir(exist_ok=True)
    env=os.environ.copy(); env.update(CUDA_VISIBLE_DEVICES='7',OMP_NUM_THREADS='2',CTX_OUT=str(out),CTX_SEED='3',CTX_K=str(k))
    with (pathlib.Path('/tmp/vio_research_loop/reviews/cycle1')/f'ctx{k}.log').open('w',buffering=1) as log:
        rc=subprocess.call([py,str(base/'context_train.py')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=7200)
    with (pathlib.Path('/tmp/vio_research_loop/reviews/cycle1')/'progress.jsonl').open('a') as f:
        f.write(json.dumps({'K':k,'rc':rc,'completed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})+'\n')
    if rc: raise SystemExit(rc)
(pathlib.Path('/tmp/vio_research_loop/reviews/cycle1')/'done').write_text('seed 3 K2 and K5 complete\n')
