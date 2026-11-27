"""summ.py RUN... : one line per run from result.json"""
import sys, json
from pathlib import Path
for r in sys.argv[1:]:
    p = Path(r) if '/' in r else Path('/data/backups/rganapa/Sebastian/gen3/agents/netv2/runs') / r
    try: j = json.load(open(p / 'result.json'))
    except Exception: print(r, 'n/a'); continue
    v = j['val']
    print(f"{p.name:14s} new {j['n_new']:4d} best_ep {j['best_epoch']:3d} all {v['all']:.4f} fast {v['fast']:.4f} zrms {v['zrms']:.2f} scale {v['scale_gt1']:.3f} "
          f"f/s/b {v['fwd']:.3f}/{v['side']:.3f}/{v['back']:.3f} cls {v['class']} reg {v['regime']} blur {v['blur']} fov {v['fov']}")
