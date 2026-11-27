import json,time,subprocess,os
from pathlib import Path
D=Path('/data/backups/rganapa/Sebastian/gen3/research/research_loop');D.mkdir(exist_ok=True)
lanes={'current_accuracy':'/tmp/vio_loop3/telemetry','fuel_and_extreme':'/tmp/vio_loop3/efficient_round2','learned_context':'/tmp/vio_loop3/context_replication','learned_geometry':'/tmp/vio_loop3/scale_init'}
start=time.monotonic();seen=set()
while time.monotonic()-start<10800:
 ps=subprocess.check_output(['ps','-eo','pid,args'],text=True).splitlines();states={}
 for name,path in lanes.items():
  root=Path(path);procs=[]
  for line in ps:
   a=line.strip().split(None,1)
   if len(a)!=2:continue
   pid,cmd=a;program=cmd.split()[0]
   if not ('python' in Path(program).name or Path(program).name=='timeout'):continue
   if path in cmd or path.replace('/tmp/','/dev/shm/') in cmd:procs.append({'pid':int(pid),'command':cmd[:400]})
  if procs:seen.add(name)
  markers=[]
  if root.exists():markers=[str(p.relative_to(root)) for p in root.glob('**/*') if p.is_file() and ('done' in p.name.lower() or p.name in ('COMPLETE','summary.json','results.tsv','results.json'))][:50]
  state='running' if procs else 'needs_review' if name in seen or markers else 'preparing'
  states[name]={'state':state,'active_processes':procs,'root':path,'markers':markers}
 status={'updated_utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()),'lanes':states,'elapsed_seconds':time.monotonic()-start,'review_policy':'Finite scripted hypotheses screen and conditionally confirm. New ideation requires a Luna review turn; this watcher does not reactivate models. needs_review may mean completed or failed: inspect logs.','best_artifact_untouched':True,'no_hidden_submissions':True,'max_local_dataset_bytes':600000000000}
 t=D/'status.json.tmp';t.write_text(json.dumps(status,indent=2)+'\n');t.replace(D/'status.json')
 if all(s['state']=='needs_review' for s in states.values()):(D/'review_needed.json').write_text(json.dumps(status,indent=2)+'\n')
 time.sleep(30)
