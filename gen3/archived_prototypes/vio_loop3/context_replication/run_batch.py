import os, subprocess, time, pathlib, json
base=pathlib.Path('/tmp/vio_loop3/context_replication')
out=pathlib.Path('/dev/shm/vio_loop3/context_replication')
py='/data/backups/rganapa/Sebastian/venv-teacher/bin/python'
script=str(base/'context_train.py')
for seed, ks in ((1,(5,)),(2,(2,5))):
  for k in ks:
    d=out/f'seed{seed}'/f'ctx{k}'; d.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy(); env.update(CUDA_VISIBLE_DEVICES='7',OMP_NUM_THREADS='2',CTX_OUT=str(d),CTX_SEED=str(seed),CTX_K=str(k))
    log=open(base/f'seed{seed}_ctx{k}.log','a',buffering=1)
    p=subprocess.Popen([py,script],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    (base/f'seed{seed}_ctx{k}.pid').write_text(str(p.pid)+'\n')
    rc=p.wait(timeout=7200)
    log.close()
    if rc: raise SystemExit(f'run seed={seed} K={k} failed rc={rc}')
    with open(base/'batch_progress.jsonl','a') as f: f.write(json.dumps({'seed':seed,'K':k,'done':time.time()})+'\n')
