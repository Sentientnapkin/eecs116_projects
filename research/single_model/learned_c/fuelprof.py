"""per-frame fuel for the first N frames on a sensor fixture: fuelprof.py wasm fixture N"""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.runner.sandbox import Sandbox
wasm, fx, n = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
with np.load(fx, allow_pickle=False) as f: d = {k: f[k].copy() for k in f.files}
box = Sandbox(wasm, log_dir=Path('/data/backups/rganapa/Sebastian/tmp/fuelprof-logs')); box.init(json.loads(str(d['camera_json'])))
out = []
for i in range(n):
    lo, hi = d['packet_offsets'][i:i + 2]; p = d['packets'][lo:hi].copy(); p[:, 0] += d['absolute_times'][0]
    r = box.step(float(d['absolute_times'][i]), d['frames'][i], p); out.append(getattr(r, 'fuel', None))
print(' '.join('%.2f' % (x / 1e6) for x in out))
