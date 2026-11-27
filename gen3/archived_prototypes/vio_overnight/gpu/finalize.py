import os,time,datetime,json
from pathlib import Path
pid=int(Path('/tmp/vio_overnight/gpu/nightmanager.pid').read_text())
d=Path('/data/backups/rganapa/Sebastian/gen3/research/overnight_20261127/gpu')
while Path(f'/proc/{pid}/cmdline').exists():
 try:
  c=Path(f'/proc/{pid}/cmdline').read_bytes()
  if not c or b'nightmanager.py' not in c: break
 except FileNotFoundError: break
 time.sleep(60)
expected=[d/stage/f'ctx{k}'/f'ctx{k}'/'result.json' for stage in ('seed4_small','seed5_large') for k in (2,5)]
complete=all(x.exists() for x in expected)
(d/'final_status.json').write_text(json.dumps({'completed':complete,'results':[str(x) for x in expected if x.exists()],'missing':[str(x) for x in expected if not x.exists()],'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
if complete:(d/'queue.complete').write_text('all queued matched stages completed before cutoff\n')
