"""Wait for >=3000 safe flights, continue selected teacher, train three student seeds."""
import json,os,subprocess,time
from pathlib import Path
H=Path(__file__).resolve().parent;PY='/data/backups/rganapa/Sebastian/venv-teacher/bin/python';BASE='/data/backups/rganapa/Sebastian'
def note(s):
 print(time.strftime('%F %T'),s,flush=True)
 with open(H/'NOTES.md','a') as f:f.write('- '+time.strftime('%F %T UTC: ')+s+'\n')
def count():
 try:return len(json.load(open(H/'tables/data_audit.json'))['train'])+len(json.load(open(H/'gen/sl_rows.json')))
 except (FileNotFoundError,json.JSONDecodeError):return 0

def start(name,gpu,args):
 env=dict(os.environ,TMPDIR=BASE+'/tmp',CUDA_VISIBLE_DEVICES=str(gpu),CUDA_CACHE_PATH=BASE+'/tmp/stlong_cuda_cache',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
 p=subprocess.Popen(['nohup',PY,'-B',str(H/'train.py'),'--name',name]+args,env=env,stdout=open(H/f'logs/{name}.log','a'),stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 path=H/'logs/jobs.json';j=json.load(open(path));j[name]=p.pid;path.write_text(json.dumps(j,indent=1));note(f'Launched {name}, GPU{gpu}, pid{p.pid}.');return p

while count()<3000:time.sleep(20)
note(f'Expanded-data training threshold reached: {count()} flights. Starting selected teacher continuation; estimate ~8min including loading, then three parallel100epoch students ~10min.')
p=start('teacher_final',3,['--nf','4','--res','128','--width','2','--deep','--hidden','256','--epochs','80','--bs','128','--lr','.0005','--init',str(H/'runs/teacher4/best.pt')])
wide=[start(f'wide{s}',gpu,['--nf','2','--res','64','--width','1.5','--hidden','128','--epochs','90','--bs','256','--seed',str(s),'--teacher',str(H/'runs/teacher4')]) for s,gpu in enumerate([1,2,4])]
assert p.wait()==0,'teacher continuation failed'
assert [q.wait() for q in wide]==[0,0,0],'wide students failed'
note('Optional width1.5 student seeds0/1/2 done; cost-aware C integration pending measured fuel gate.')
selected_teacher=min(['teacher4','teacher_final'],key=lambda n:json.load(open(H/'runs'/n/'result.json'))['best_crit'])
note(f'Selected {selected_teacher} by pooled direct/high-speed criterion; launching three lcJ student seeds0/1/2,100epochs each.')
procs=[start(f'student{s}',gpu,['--nf','2','--res','64','--width','1','--hidden','128','--epochs','100','--bs','256','--seed',str(s),'--teacher',str(H/'runs'/selected_teacher),'--init',str(H/'runs/baseline/best.pt'),'--lr','.0008']) for s,gpu in enumerate([1,2,3])]
rc=[p.wait() for p in procs];assert rc==[0,0,0],rc
note('Three expanded-data student runs DONE. In-filter screening and final evaluation pending.')
