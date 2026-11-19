"""Independent actual-Wasm prefix with calibrated sensor times; compares all emitted pose/twist."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from viobench.tools.runner.sandbox import Sandbox

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('build', type=Path);p.add_argument('fixture', type=Path);p.add_argument('full', type=Path)
p.add_argument('--frames', type=int, default=600);p.add_argument('--out', type=Path, required=True);a = p.parse_args()
f = dict(np.load(a.fixture));expected = np.load(a.full)['wasm'][:a.frames]
guest = Sandbox(a.build / 'odometry.wasm', log_dir=a.out.parent / (a.out.stem + '-logs'))
guest.init(json.loads(str(f['camera_json'])))
debug = guest.instance.exports(guest.store)['input_features']
pointers = [guest.alloc(n) for n in (5 * 96 * 128, 51 * 4, 9 * 8, 13 * 8)]
out = [];offsets = f['packet_offsets'];origin = float(f['absolute_times'][0])
for i in range(a.frames):
    packet = f['packets'][offsets[i]:offsets[i+1]].copy();packet[:, 0] += origin
    row = guest.step(float(f['absolute_times'][i]), f['frames'][i], packet)
    out.append(np.r_[row.pose, row.twist]);debug(guest.store, *pointers)
out = np.stack(out)
d = {'wasm_sha256': hashlib.sha256((a.build/'odometry.wasm').read_bytes()).hexdigest(), 'frames':len(out),
     'emitted_pose_and_twist_prefix_exact':bool(np.array_equal(out, expected)),
     'max_component_delta':float(np.abs(out-expected).max()),
     'first_camera_pose_exact':bool(np.array_equal(out[0,:7],[0,0,0,0,0,0,1])),
     'first_camera_timestamp':origin,'future_measurements_supplied':False}
a.out.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2),flush=True)
assert d['emitted_pose_and_twist_prefix_exact'] and d['first_camera_pose_exact']
