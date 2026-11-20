import json, glob, hashlib
from pathlib import Path
import numpy as np
B='/data/backups/rganapa/Sebastian/gen/raw-fast/bench'
sel={p.stem for p in Path('/data/backups/rganapa/Sebastian/gen/raw-fast/selected').glob('*.zip')}
rows={}
for f in glob.glob(B+'/*.json'):
    d=json.load(open(f)); ep=d['id']; a=d['audit']
    fo=int(hashlib.sha256((d['catalog']+':'+d['scene']).encode()).hexdigest()[:8],16)%5
    o=d.get('task_overrides',{})
    rows[ep]=dict(pool='sel' if ep in sel else 'fresh',fold=fo,start='mid' if ep.startswith('fastmid') else 'static',scene=d['scene'],catalog=d['catalog'],setting=d.get('setting'),
      travel=a['travel_m'],zm=a['zero_motion_ate_m'],sp=a['speed_p10_p50_p90'],hover=a['hover_fraction'],back=a['backward_fraction'],lat=a['lateral_fraction'],vert=a['vertical_fraction'],
      turn=a['turning_fraction'],dark=a['dark_fraction'],flat=a['flat_fraction'],flags=a['flags'],cruise=(o.get('CRUISE_SPEED_MIN'),o.get('CRUISE_SPEED_MAX')),maxyaw=o.get('MAX_YAW_RATE'),fov=d['simulator'].get('fov'),
      hold=d.get('hold_seconds'),wps=d.get('waypoints_per_second'),maxacc=o.get('MAX_ACCELERATION'))
json.dump(rows,open('research/single_model/edge/audit.json','w'))
print(len(rows))
import collections
for pool in ('sel','fresh'):
  for st in ('static','mid'):
    r=[v for v in rows.values() if v['pool']==pool and v['start']==st and v['fold']!=4]
    print(pool,st,len(r),'travel mean %.1f med %.1f'%(np.mean([x['travel'] for x in r]),np.median([x['travel'] for x in r])),'zm mean %.2f'%np.mean([x['zm'] for x in r]), 'cruise',collections.Counter(x['cruise'] for x in r).most_common(3),'fov',collections.Counter(x['fov'] for x in r).most_common(3),'setting',collections.Counter(x['setting'] for x in r).most_common(3))
