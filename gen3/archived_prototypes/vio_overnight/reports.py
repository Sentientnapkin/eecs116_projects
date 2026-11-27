"""Overnight local progress snapshots. Does not send chat messages or call AI models."""
import json,time,datetime,subprocess
from pathlib import Path
UTC=datetime.timezone.utc
ROOT=Path('/data/backups/rganapa/Sebastian/gen3/research/overnight_20261127');OUT=ROOT/'reports';OUT.mkdir(parents=True,exist_ok=True)
TIMES=[datetime.datetime(2026,11,27,h,0,tzinfo=UTC) for h in (12,14,16)]
SOURCES={'gpu':'/tmp/vio_overnight/gpu','classical':'/tmp/vio_overnight/classical','prior_review':'/tmp/vio_research_loop/reviews','context_replication':'/tmp/vio_loop3/context_replication','depth':'/tmp/vio_overnight/depth','gpu_results':str(ROOT/'gpu'),'classical_results':str(ROOT/'classical'),'depth_results':str(ROOT/'depth')}
def snapshot(label):
 now=datetime.datetime.now(UTC); ps=subprocess.check_output(['ps','-eo','pid,etime,args'],text=True).splitlines();jobs={}
 for name,path in SOURCES.items():
  root=Path(path);active=[]
  for line in ps:
   a=line.strip().split(None,2)
   if len(a)!=3:continue
   pid,elapsed,cmd=a;program=Path(cmd.split()[0]).name
   if ('python' in program or program=='timeout') and (path in cmd or path.replace('/tmp/','/dev/shm/') in cmd):active.append({'pid':int(pid),'elapsed':elapsed,'command':cmd[:350]})
  files=[]
  if root.exists():files=[{'path':str(p),'bytes':p.stat().st_size,'mtime':p.stat().st_mtime} for p in root.rglob('*') if p.is_file() and (p.suffix=='.json' or p.name in ('COMPLETE','queue.done','review_needed','status.jsonl'))][-80:]
  jobs[name]={'active_processes':active,'artifacts':files}
 metrics=[]
 for base in [str(ROOT/'gpu'),str(ROOT/'depth'),'/dev/shm/vio_overnight/gpu','/dev/shm/vio_loop3/context_replication','/dev/shm/vio_research_loop/reviews']:
  p=Path(base)
  if not p.exists():continue
  for f in p.rglob('result.json'):
   try:
    d=json.loads(f.read_text());metrics.append({'path':str(f),'metrics':{k:d[k] for k in ['all','median','p90','fast_err','speed_abs_err','speed_bias','dir_deg_gt1','zrms','params','K','seed','variant'] if k in d}})
   except (ValueError,OSError):pass
 report={'timestamp_utc':now.isoformat(),'label':label,'delivery':'local progress report; proactive chat scheduling unavailable','cutoff_utc':'2026-11-27T16:00:00+00:00','jobs':jobs,'learned_validation':metrics,'constraints':{'luna_review_only':'brief setup/review; compute in scripts','best_artifact_unchanged':True,'no_hidden_submissions':True,'local_dataset_cap_bytes':600000000000},'caveat':'Read each experiment manifest for matched baseline and sample count. Validation error is not downstream ATE or measured WASM fuel.'}
 f=OUT/(now.strftime('%Y%m%dT%H%M%SZ')+'_'+label+'.json');f.write_text(json.dumps(report,indent=2)+'\n');(OUT/'latest.json').write_text(json.dumps(report,indent=2)+'\n')
 lines=[f'VIO research progress: {now.isoformat()}', 'Local report only; chat delivery is unavailable.', 'Overnight cutoff: 08:00 Pacific / 16:00 UTC.', '']
 for name,j in jobs.items():
  lines.append(f'{name}: {len(j["active_processes"])} active processes; {len(j["artifacts"])} result/status artifacts')
 lines.append('')
 for item in metrics:
  m=item['metrics']; lines.append(f'{item["path"]}: mean velocity error={m.get("all","unknown")} m/s, fast error={m.get("fast_err","unknown")} m/s, K={m.get("K","unknown")}')
 lines+=['', 'Validation error is not downstream trajectory ATE or measured WASM fuel.', 'Current best preserved; no hidden evaluation submissions.']
 f.with_suffix('.txt').write_text('\n'.join(lines)+'\n');(OUT/'latest.txt').write_text('\n'.join(lines)+'\n')
 (ROOT/'report_schedule.json').write_text(json.dumps({'delivery':'local files only, no chat delivery','scheduled_utc':[t.isoformat() for t in TIMES],'latest_report':str(f)},indent=2)+'\n')
snapshot('initial')
for target in TIMES:
 while True:
  wait=(target-datetime.datetime.now(UTC)).total_seconds()
  if wait<=0:break
  time.sleep(min(60,wait))
 snapshot(target.strftime('scheduled_%H%MUTC'))
(ROOT/'reports.done').write_text('all three local progress snapshots produced\n')
