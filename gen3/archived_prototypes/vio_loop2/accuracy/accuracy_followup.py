import json,sys,time,statistics
from pathlib import Path
sys.path.insert(0,'/tmp/vio_loop2/accuracy')
import run_accuracy as A
W=A.W
if A.sha(A.BASE)!=A.BASESHA:raise RuntimeError('baseline mismatch')
control=A.build('same_source_control')
if A.sha(control)!=A.BASESHA:raise RuntimeError('control rebuild mismatch')
confbase=json.loads((A.SH/'confirm48_baseline.json').read_text())
screenbase=json.loads((A.SH/'screen24_baseline.json').read_text())
results={}; confirmed=[]
depth=A.O/'builds/depth25/solution.wasm'
r=A.evalone('depth25',depth,'confirm48'); ss=A.stats(r,confbase)
results['depth25']={'stage':'confirm48','result':r,'paired':ss}
A.log('FOLLOWUP CONFIRM depth25 '+json.dumps(ss))
if ss['mean_delta']<0 and ss['ci95'][1]<0:confirmed.append('depth25')
for name,flags in [('tri_cond1','TRI_MIN_EIG=1e-5'),('tri_cond2','TRI_MIN_EIG=1e-4')]:
 w=A.build(name,flags)
 r=A.evalone(name,w,'screen24');ss=A.stats(r,screenbase)
 results[name]={'stage':'screen24','result':r,'paired':ss}
 A.log('FOLLOWUP SCREEN '+name+' '+json.dumps(ss))
 if ss['mean_delta']<-.01 and ss['max_regression']<.4:
  r=A.evalone(name,w,'confirm48');ss=A.stats(r,confbase)
  results[name]['confirmation']={'result':r,'paired':ss}
  A.log('FOLLOWUP CONFIRM '+name+' '+json.dumps(ss))
  if ss['mean_delta']<0 and ss['ci95'][1]<0:confirmed.append(name)
(W/'followup_summary.json').write_text(json.dumps({'results':results,'confirmed':confirmed},indent=2)+'\n')
(W/'followup.done').write_text('depth confirmation and two active triangulation thresholds complete\n')
