import time,datetime,os,signal,shutil,json
from pathlib import Path
END=datetime.datetime(2026,11,27,16,tzinfo=datetime.timezone.utc).timestamp()
while time.time()<END+5:time.sleep(min(60,END+5-time.time()))
patterns=[b'/tmp/vio_overnight/gpu/context_train.py',b'/tmp/vio_overnight/gpu/wide_teacher.py',b'/tmp/vio_overnight/gpu/nightmanager.py',b'/tmp/vio_overnight/gpu/conditional_teacher.py']
stopped=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  cmd=(p/'cmdline').read_bytes()
  if any(x in cmd for x in patterns):os.kill(int(p.name),signal.SIGTERM);stopped.append({'pid':int(p.name),'command':cmd.replace(b'\0',b' ').decode(errors='replace')[:500]})
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
D=Path('/data/backups/rganapa/Sebastian/gen3/research/overnight_20261127');snap=D/'cutoff_checkpoints';snap.mkdir(exist_ok=True)
for src in Path('/dev/shm/vio_overnight/gpu').rglob('last.pt'):
 target=snap/src.relative_to('/dev/shm/vio_overnight/gpu');target.parent.mkdir(parents=True,exist_ok=True)
 try:shutil.copy2(src,target)
 except OSError:pass
(D/'cutoff.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'terminated_owned_gpu_processes':stopped,'note':'Only explicitly owned overnight GPU commands matched; no other user jobs were stopped. Last checkpoints may represent incomplete experiments.'},indent=2)+'\n')
