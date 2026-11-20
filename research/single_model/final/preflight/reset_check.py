"""Re-init in one instance: run N frames, call the real ABI init again, replay; also a partial replay then re-init.
Compare with the first replay (same process) -- the caller compares with a fresh process via the saved .first.npy."""
import sys, json, hashlib, os
from pathlib import Path
import numpy as np
sys.path.insert(0, os.environ.get('VIOBENCH_SRC', '/dev/shm/sebastian-vio/viobench'))
from viobench.tools.runner.sandbox import Sandbox
wasm, fixture, n, out = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
with np.load(fixture, allow_pickle=False) as f: data = {k: f[k].copy() for k in f.files}
camera = json.loads(str(data['camera_json'])); n = min(n, len(data['frames']))
out.parent.mkdir(parents=True, exist_ok=True)
box = Sandbox(wasm, log_dir=out.parent / (out.stem + '-logs')); box.init(camera)


def replay(m):
    s = []
    for i in range(m):
        lo, hi = data['packet_offsets'][i:i + 2]
        p = data['packets'][lo:hi].copy(); p[:, 0] += data['absolute_times'][0]
        r = box.step(float(data['absolute_times'][i]), data['frames'][i], p); s.append(np.r_[r.pose, r.twist])
    return np.asarray(s)


def reinit():
    enc = json.dumps(camera).encode(); ptr = box.alloc(len(enc)); box.write(ptr, enc)
    box._arm(box.limits.init_fuel, box.limits.init_wall_seconds)
    return box._guard(lambda: box._init(box.store, ptr, len(enc)))


first = replay(n)
st = reinit(); second = replay(n)
replay(min(137, n)); st3 = reinit(); third = replay(n)
res = dict(wasm_sha256=hashlib.sha256(wasm.read_bytes()).hexdigest(), fixture=fixture.name, frames=n, init2_status=st, init3_status=st3,
           second_equals_first=bool(np.array_equal(first, second)), after_partial_equals_first=bool(np.array_equal(first, third)),
           first_pose_identity=bool(np.array_equal(second[0, :7], [0, 0, 0, 0, 0, 0, 1])))
np.save(out.with_suffix('.first.npy'), first)
print(json.dumps(res)); out.write_text(json.dumps(res) + '\n')
