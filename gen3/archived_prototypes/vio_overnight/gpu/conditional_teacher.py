import os,time,json,subprocess,datetime,shutil
from pathlib import Path
B=Path('/tmp/vio_overnight/gpu');D=Path('/data/backups/rganapa/Sebastian/gen3/research/overnight_20261127/gpu');T=Path('/dev/shm/vio_overnight/gpu/seed6_wide');PY='/data/backups/rganapa/Sebastian/venv-teacher/bin/python'
END=datetime.datetime(2026,11,27,16,tzinfo=datetime.timezone.utc).timestamp()
def log(message):
 with (D/'conditional_teacher.log').open('a') as f:f.write(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'message':message})+'\n')
def alive(pid,part):
 try:return part.encode() in Path(f'/proc/{pid}/cmdline').read_bytes()
 except (FileNotFoundError,ProcessLookupError):return False
pid=int((B/'nightmanager.pid').read_text());log('waiting for matched 100-epoch curriculum before capacity decision')
while alive(pid,'/tmp/vio_overnight/gpu/nightmanager.py') and time.time()<END:time.sleep(60)
results={}
for k in (2,5):
 p=D/'seed5_large'/f'ctx{k}'/f'ctx{k}'/'result.json'
 if not p.exists():log('skip: incomplete larger-data matched control');sys_exit=0;break
 results[k]=json.loads(p.read_text())
if len(results)==2:
 a,b=results[2],results[5]
 passed=b['all']<.99*a['all'] and b['fast_err']<a['fast_err'] and b['tail_gt1']<=1.10*a['tail_gt1']
 decision={'passed':passed,'matched_k2':a['all'],'matched_k5':b['all'],'gate':'at least 1% vector-error improvement, improved fast error, no >10% increase in >1m/s errors','capacity_channels':[32,48,64,96],'seed':6,'epochs':200,'arms':[2,5]}
 (D/'conditional_teacher_decision.json').write_text(json.dumps(decision,indent=2)+'\n')
 if passed and END-time.time()>14400:
  while time.time()<END-14400:
   mem=int(subprocess.check_output(['nvidia-smi','--id=7','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
   if mem<500:break
   log('GPU7 occupied after curriculum; waiting, no other job disturbed');time.sleep(60)
  else:passed=False;log('skip: insufficient remaining time for matched wide pair')
  if passed:
   for k in (2,5):
    if time.time()>=END:break
    out=T/f'ctx{k}';out.mkdir(parents=True,exist_ok=True);dest=D/'seed6_wide'/f'ctx{k}';dest.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='7',OMP_NUM_THREADS='2',CTX_OUT=str(out),CTX_SEED='6',CTX_K=str(k),CTX_TRAIN_LIST='trainall1.txt',CTX_JOB_SECONDS=str(max(1,int(END-time.time()))))
    log(f'start matched wide teacher K{k}')
    with (dest/'train.log').open('a') as f:
     try:rc=subprocess.call([PY,str(B/'wide_teacher.py')],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=max(1,int(END-time.time())))
     except subprocess.TimeoutExpired:rc=124
    for p in out.iterdir():
     if p.is_dir():shutil.copytree(p,dest/p.name,dirs_exist_ok=True)
     else:shutil.copy2(p,dest/p.name)
    log(f'finished K{k}, returncode={rc}')
    if rc:break
 else:log('skip: gate failed or less than four hours left')
(D/'conditional_teacher.done').write_text('conditional teacher decision completed; inspect per-arm completion\n')
