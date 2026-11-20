"""Prefix / causality check: for each fixture, run the full replay once (fresh instance) and, for each prefix length n, a fresh instance replaying only the first n frames;
outputs (pose+twist) must be bit-equal to the first n outputs of the full run (the guest cannot see frames > n; this is the future-poison equivalence: sensors beyond n do not exist for it).
Also a poison variant: fixture frames/IMU beyond n replaced by garbage in a SECOND replay that is cut at n+1 (first n outputs must still match).
  prefix_check.py wasm fixture.npz out.json"""
import sys, json, os
from pathlib import Path
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.runner.sandbox import Sandbox
wasm, fixture, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
with np.load(fixture, allow_pickle=False) as f: data = {k: f[k].copy() for k in f.files}
camera = json.loads(str(data['camera_json']))
PREFIXES = [1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 40, 41, 120, 600, 1199]
def replay(n, poison_after=None, tag='x'):
    box = Sandbox(wasm, log_dir=out.parent / f'{out.stem}-{tag}-logs'); box.init(camera); s = []
    rng = np.random.default_rng(1)
    for i in range(min(n, len(data['frames']))):
        lo, hi = data['packet_offsets'][i:i + 2]
        p = data['packets'][lo:hi].copy(); p[:, 0] += data['absolute_times'][0]; fr = data['frames'][i]
        if poison_after is not None and i >= poison_after:
            fr = rng.integers(0, 256, fr.shape, dtype=np.uint8); p[:, 1:] = rng.normal(0, 50, p[:, 1:].shape)
        r = box.step(float(data['absolute_times'][i]), fr, p); s.append(np.r_[r.pose, r.twist])
    return np.asarray(s)
full = replay(1200, tag='full'); res = {'fixture': fixture.name, 'frames': len(full), 'cases': []}
full2 = replay(1200, tag='full2'); res['repeat_equal'] = bool(np.array_equal(full, full2))
for n in PREFIXES:
    n = min(n, len(full)); a = replay(n, tag=f'p{n}'); b = replay(min(n + 3, len(full)), poison_after=n, tag=f'q{n}')
    res['cases'].append(dict(n=n, prefix_equal=bool(np.array_equal(a, full[:n])), poison_equal=bool(np.array_equal(b[:n], full[:n]))))
res['all_pass'] = res['repeat_equal'] and all(c['prefix_equal'] and c['poison_equal'] for c in res['cases'])
out.write_text(json.dumps(res)); print(fixture.name, 'repeat', res['repeat_equal'], 'cases pass', sum(c['prefix_equal'] and c['poison_equal'] for c in res['cases']), '/', len(res['cases']), flush=True)
