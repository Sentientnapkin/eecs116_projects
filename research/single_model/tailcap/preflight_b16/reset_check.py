"""re-init replay + partial-then-reinit replay on 8 fixtures (folds 0-3 fixtures from final/preflight_c1_fbh/fixtures_list.txt), 700 frames (covers re-anchor window)."""
import json, sys
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from pathlib import Path
from viobench.tools.runner.sandbox import Sandbox
W = Path('research/single_model/tailcap/gp_msckf_startup_b16.wasm')
FX = Path('research/results/single_model/preflight_c1_fx')
L = [l.strip() for l in open('research/single_model/final/preflight_c1_fbh/fixtures_list.txt') if l.strip()]
pick = [L[i] for i in (0, 1, 2, 9, 10, 11, 12, 16)]
N = 700
def run(box, f, n, init=True):
    cam = json.loads(str(f["camera_json"])); box.initialized = False; box.init(cam)
    out = []
    for i in range(n):
        p = f['packets'][f['packet_offsets'][i]:f['packet_offsets'][i + 1]].copy(); p[:, 0] += f['absolute_times'][0]
        r = box.step(float(f['absolute_times'][i]), f['frames'][i], p); out.append(np.r_[r.pose, r.twist])
    return np.asarray(out)
ok = True
for nm in pick:
    with np.load(FX / (nm + '.npz'), allow_pickle=False) as z: f = {k: z[k].copy() for k in z.files}
    box = Sandbox(W, log_dir=Path('/data/backups/rganapa/Sebastian/tmp/b16_reset_logs') / nm)
    a = run(box, f, N)
    b = run(box, f, N)                       # re-init replay
    run(box, f, 150)                         # partial
    c = run(box, f, N)                       # re-init after partial
    box2 = Sandbox(W, log_dir=Path('/data/backups/rganapa/Sebastian/tmp/b16_reset_logs') / (nm + '_p2'))
    d = run(box2, f, N)                      # fresh process equal
    res = dict(fixture=nm, frames=N, second_equals_first=bool(np.array_equal(a, b)), after_partial_equals_first=bool(np.array_equal(a, c)),
               fresh_process_equal=bool(np.array_equal(a, d)), first_pose_identity=bool(np.allclose(a[0, :6], 0) and a[0, 6] == 1))
    ok &= all(v for k, v in res.items() if k not in ('fixture', 'frames')); print(json.dumps(res), flush=True)
print('RESET', 'PASS' if ok else 'FAIL')
