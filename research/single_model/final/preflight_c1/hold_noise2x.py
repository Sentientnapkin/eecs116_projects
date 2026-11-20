"""Static fixtures: perturb IMU of the first NF frames (incl. frame-0 window) with extra white noise so per-sample noise std is K x nominal (0.28 m/s2, 0.07 rad/s),
replay the first NF frames in the GATE_DEBUG=3 build (state-identical to the candidate), decode hold counters from the last row."""
import sys, json, numpy as np
from pathlib import Path
from viobench.tools.runner.sandbox import Sandbox
wasm, NF = Path(sys.argv[1]), 60
K = float(sys.argv[2]); fixtures = sys.argv[3:]
res = []
for fx in fixtures:
    with np.load(fx, allow_pickle=False) as f: d = {k: f[k].copy() for k in f.files}
    camera = json.loads(str(d['camera_json']))
    for seed in (0, 1, 2):
        rng = np.random.default_rng(1000 + seed)
        box = Sandbox(wasm, log_dir=Path('/dev/shm/sebastian-vio/c1_n2x_logs')); box.init(camera)
        extra = np.sqrt(K * K - 1)
        last = None
        for i in range(NF):
            lo, hi = d['packet_offsets'][i:i + 2]; p = d['packets'][lo:hi].copy()
            if K != 1.0:
                p[:, 1:4] += rng.normal(0, 0.28 * extra, p[:, 1:4].shape); p[:, 4:7] += rng.normal(0, 0.07 * extra, p[:, 4:7].shape)
            p[:, 0] += d['absolute_times'][0]
            r = box.step(float(d['absolute_times'][i]), d['frames'][i], p); last = r.pose[:3]
            if K == 1.0 and seed: break
        if K == 1.0 and seed: continue
        x, y, z = int(round(last[0])), int(round(last[1])) + 1, int(round(last[2]))
        res.append(dict(fixture=Path(fx).stem, K=K, seed=seed, n_active=x % 10000, runmax=x // 10000, off_frame=y % 10000 - 1,
                        reason={0: 'none', 1: 'time', 2: 'gyro>0.12', 3: '|f|-g>1'}[(y // 10000) % 100], first=y // 1000000 - 1, moving=z % 10, last=z // 10 - 1))
        print(json.dumps(res[-1]), flush=True)
