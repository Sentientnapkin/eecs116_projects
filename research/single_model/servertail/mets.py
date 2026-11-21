"""mets.py EVALDIR OUT.json : collect per-episode report metrics + generator audit features"""
import json, sys, glob, os
from pathlib import Path
ev = Path(sys.argv[1]); rows = []
src = ['/data/backups/rganapa/Sebastian/tmp/fresh_pool', '/data/backups/rganapa/Sebastian/gen/raw-fast/bench', '/data/backups/rganapa/Sebastian/gen/raw-fast/selected']
extra = os.environ.get('POOL')
if extra: src.insert(0, extra)
for rj in sorted(ev.glob('*/report/report.json')):
    ep = rj.parent.parent.name
    m = json.loads(rj.read_text())['episodes'][0]
    me = m['metrics']; r = dict(ep=ep, peak=m['fuel_per_frame_max'], ok=m['completed'])
    r.update({k: me.get(k) for k in ['ate_rmse', 'rotation_rmse', 'velocity_rmse', 'sim3_scale', 'sim3_ate_rmse', 'distance_travelled', 'final_drift', 'filled_frames']})
    for s in src:
        f = Path(s) / f'{ep}.json'
        if f.exists():
            d = json.loads(f.read_text()); a = d.get('audit', {})
            r.update(v90=a.get('speed_p10_p50_p90', [0, 0, 0])[2], v50=a.get('speed_p10_p50_p90', [0, 0, 0])[1], turn=a.get('turning_fraction'),
                     zm=a.get('zero_motion_ate_m'), cat=d.get('catalog'), scene=d.get('scene'), crop=d.get('crop_start_s'), to=d.get('task_overrides'),
                     wps=d.get('waypoints_per_second'), regime=d.get('regime'))
            break
    rows.append(r)
Path(sys.argv[2]).write_text(json.dumps(rows))
print(len(rows))
