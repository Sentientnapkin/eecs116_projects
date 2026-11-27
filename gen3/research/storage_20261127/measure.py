import subprocess,json
from pathlib import Path
base=Path('/data/backups/rganapa/Sebastian')
roots=[base/'gen',base/'gen3/out',base/'gen3/agents/net/cache',base/'gen3/twin/zips',base/'gen3/pilot',base/'gen3/scenes',base/'eecs116_projects/research/data',base/'gen3/research',base/'tmp/stlearn_hf',Path('/dev/shm/vio_fourlane_20261127'),Path('/tmp/vio-research-20261126')]
r=subprocess.run(['du','-x','-B1','-sc',*[str(p) for p in roots]],capture_output=True,text=True)
Path('/tmp/vio_storage_20261127/usage.txt').write_text(r.stdout+r.stderr)
rows=[]
for line in r.stdout.splitlines():
 n,p=line.split('\t',1);rows.append(dict(bytes=int(n),path=p))
total=next(x['bytes'] for x in rows if x['path']=='total')
Path('/tmp/vio_storage_20261127/usage.json').write_text(json.dumps(dict(cap_bytes=600000000000,measured_bytes=total,under_cap=total<=600000000000,roots=rows,note='Conservative includes entire legacy gen and research directories; one du invocation counts hardlinks once.'),indent=2)+'\n')
