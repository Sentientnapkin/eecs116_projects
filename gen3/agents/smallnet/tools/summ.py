"""summ.py [RUN...]: one line per smallnet run (best val so far, macs, cfg)"""
import sys, json, glob
from pathlib import Path
R = Path('/data/backups/rganapa/Sebastian/gen3/agents/smallnet/runs')
runs = sys.argv[1:] or sorted(p.name for p in R.iterdir() if (p / 'result.json').exists())
for r in runs:
    try: j = json.load(open(R / r / 'result.json'))
    except Exception: continue
    c = j['cfg']; v = j.get('val'); lg = j['log']
    b = min(lg, key=lambda x: x['val']['all']) if lg else None
    v = v or (b['val'] if b else {})
    print(f"{r:14s} {'DONE' if 'val' in j else 'ep%3d' % (len(lg) - 1)} all {v.get('all', 0):.4f} fast {v.get('fast', 0):.4f} zrms {v.get('zrms', 0):.2f} f/s/b {v.get('fwd', 0):.3f}/{v.get('side', 0):.3f}/{v.get('back', 0):.3f} "
          f"macs {c.get('macs', 0)/1e6:.3f}M chs {c['chs']} pre {c['pre']} res {c['res']} cin {c['cin']} hid {c['hid']} kd {c['kd']}")
