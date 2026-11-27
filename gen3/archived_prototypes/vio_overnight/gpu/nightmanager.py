#!/usr/bin/env python3
import os,sys,time,json,subprocess,shutil,datetime
from pathlib import Path
BASE=Path('/tmp/vio_overnight/gpu'); SRC=Path('/tmp/vio_overnight/gpu/context_train.py')
TMP=Path('/dev/shm/vio_overnight/gpu'); DUR=Path('/data/backups/rganapa/Sebastian/gen3/research/overnight_20261127/gpu')
PY='/data/backups/rganapa/Sebastian/venv-teacher/bin/python'
DEADLINE= datetime.datetime(2026,11,27,16,0,0,tzinfo=datetime.timezone.utc).timestamp()
PIDS=(460403,461942)

def alive_matching(pid,needle):
 p=Path(f'/proc/{pid}/cmdline')
 try: cmd=p.read_bytes().replace(b'\0',b' ').decode(errors='replace')
 except (FileNotFoundError,ProcessLookupError): return False
 return needle in cmd

def log(msg):
 with (DUR/'nightmanager.log').open('a') as f: f.write(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'message':msg})+'\n');f.flush();os.fsync(f.fileno())

def wait_current():
 while any(alive_matching(p,'launch_seed3.py') if p==460403 else alive_matching(p,'context_train.py') for p in PIDS):
  log('waiting for seed3 launcher/child to exit; no GPU7 work started')
  time.sleep(60)

stages=[('seed4_small',4,'train727.txt'),('seed5_large',5,'trainall1.txt')]
(DUR/'manifest.json').write_text(json.dumps({'deadline_utc':'2026-11-27T16:00:00Z','gpu':'7 only','stages':[{'name':n,'seed':s,'train_list':l,'arms':[2,5],'epochs':100,'steps_per_epoch':400,'batch_size':256} for n,s,l in stages],'notes':'Existing caches only; matched K2/K5 pairs; common validation anchors pos>=3; CPU threads=2. Seed is applied before smoke/model init and reset before run. Output checkpoints live in /dev/shm; final model and prediction summaries copied here.'},indent=2)+'\n')
wait_current()
for stage,seed,train_list in stages:
 if time.time()>=DEADLINE: log('cutoff reached before '+stage);break
 # Complete K2 then K5 within each matched stage. Failure halts queue.
 for k in (2,5):
  if time.time()>=DEADLINE: log('cutoff reached before '+stage+f' K{k}');break
  out=TMP/stage/f'ctx{k}';out.mkdir(parents=True,exist_ok=True)
  dest=DUR/stage/f'ctx{k}';dest.mkdir(parents=True,exist_ok=True)
  remaining=int(DEADLINE-time.time())
  env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='7',OMP_NUM_THREADS='2',CTX_OUT=str(out),CTX_SEED=str(seed),CTX_K=str(k),CTX_TRAIN_LIST=train_list,CTX_JOB_SECONDS=str(remaining))
  with (dest/'train.log').open('a') as f:
   log(f'start {stage} K{k}, seed={seed}, list={train_list}, remaining={remaining}s')
   rc=subprocess.call([PY,str(SRC)],env=env,stdout=f,stderr=subprocess.STDOUT)
  # Persist every produced artifact and record status, even on failure.
  for p in out.iterdir():
   if p.is_file(): shutil.copy2(p,dest/p.name)
   elif p.is_dir(): shutil.copytree(p,dest/p.name,dirs_exist_ok=True)
  pred=dest/f'ctx{k}_val_predictions.npz'
  if pred.exists(): subprocess.run([PY,str(BASE/'analyze_errors.py'),str(pred)],check=True)
  status={'stage':stage,'seed':seed,'K':k,'returncode':rc,'complete':(rc==0 and (out/f'ctx{k}'/'result.json').exists()),'remaining_seconds':max(0,int(DEADLINE-time.time()))}
  (dest/'status.json').write_text(json.dumps(status,indent=2)+'\n');log(json.dumps(status))
  if rc!=0: log('failed; stopping queue, not marking completion');sys.exit(rc)
# Only claim complete when all four results are present.
expected=[DUR/s/f'ctx{k}'/'result.json' for s,_,_ in stages for k in (2,5)]
if all(x.exists() for x in expected):
 (DUR/'queue.complete').write_text('all queued matched stages completed before cutoff\n');log('all queued stages complete')
else: log('cutoff/incomplete queue; no completion marker')
