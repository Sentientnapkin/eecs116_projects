"""bit-compare two wasms on a fixture (pose+twist all frames): cmpwasm.py a.wasm b.wasm fixture [n]"""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.runner.sandbox import Sandbox
fx = Path(sys.argv[3]); n = int(sys.argv[4]) if len(sys.argv) > 4 else 300
with np.load(fx, allow_pickle=False) as f: d = {k: f[k].copy() for k in f.files}
res = []
for w in sys.argv[1:3]:
    box = Sandbox(Path(w), log_dir=Path('/data/backups/rganapa/Sebastian/tmp/cmpwasm-logs')); box.init(json.loads(str(d['camera_json']))); s = []
    for i in range(min(n, len(d['frames']))):
        lo, hi = d['packet_offsets'][i:i + 2]; p = d['packets'][lo:hi].copy(); p[:, 0] += d['absolute_times'][0]
        r = box.step(float(d['absolute_times'][i]), d['frames'][i], p); s.append(np.r_[r.pose, r.twist])
    res.append(np.asarray(s))
print(fx.name, 'bit-equal', bool(np.array_equal(res[0], res[1])), 'frames', len(res[0]))
