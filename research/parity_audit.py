"""Measure Python/native/Wasm attitude agreement, retaining numerical failures."""
import concurrent.futures
import ctypes as ct
import json
from pathlib import Path
import re
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'frozen_reference'))
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from common import Flight
import attitude_bias as ab
from viobench.tools.datasets.storage import read_episode

OUT = ROOT / 'results/loop/fusion-completion'


def quaternion_rotation(q):
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def one(archive):
    cv2.setNumThreads(1)
    flight = Flight(archive)
    expected, count, _ = ab.attitudes(flight, 'kf_grid')
    results = {}
    for arm in ('kf_grid', 'knownrot_a_replace'):
        work = OUT / f'public-n2-218-{arm}-parity-repair-trace' / archive.stem / 'report/logs'
        log = next(work.glob('*/estimate.tum'))
        data = np.loadtxt(log)
        rbc = flight.T_bc[:3, :3]
        got = np.stack([rbc @ quaternion_rotation(q) @ rbc.T for q in data[:, 4:8]])
        angles = np.degrees([np.linalg.norm(ab.log_so3(a.T @ b)) for a, b in zip(expected, got)])
        stderr = (log.parent / 'stderr.txt').read_text()
        accepted = len(re.findall(r'win t=.* ok ', stderr))
        rejected = len(re.findall(r'win t=.* rejected ', stderr))
        results[arm] = {'max_angle_deg': float(max(angles)), 'final_angle_deg': float(angles[-1]),
                        'accepted_wasm': accepted, 'rejected_wasm': rejected,
                        'accepted_python': count['accepted'], 'rejected_python': count['rejected']}
    return {'episode': archive.stem, 'python_opencv': cv2.__version__, 'arms': results}


def native(archive, version='4.12.0'):
    # The final explicit native build uses the same OpenCV4.12 sources as Wasm.
    build = OUT / 'artifacts/n2-218-knownrot_a_replace-parity-repair-trace'
    lib = ct.CDLL(str(build / 'host_visual.so'))
    arr = lambda dtype: np.ctypeslib.ndpointer(dtype=dtype, flags='C_CONTIGUOUS')
    lib.host_weights.argtypes = [arr(np.float32)]
    lib.init.argtypes = [ct.c_char_p, ct.c_uint32]
    lib.step.argtypes = [ct.c_double, arr(np.uint8), arr(np.float64), ct.c_int32, arr(np.float64)]
    weights = np.fromfile(build / 'weights.f32', dtype='<f4');lib.host_weights(weights)
    ep = read_episode(archive);camera, images = ep.adapt((320, 240))
    config = json.dumps(camera).encode();assert lib.init(config, len(config)) == 0
    native_rows = np.empty((ep.num_frames, 13), np.float64)
    for i, t in enumerate(ep.frame_times):
        packet = np.ascontiguousarray(ep.imu_window(i), np.float64)
        assert lib.step(float(t), np.ascontiguousarray(images[i]), packet, len(packet), native_rows[i]) == 0
    assert lib.init(config, len(config)) == 0
    prefix = np.empty((26, 13), np.float64)
    for i, t in enumerate(ep.frame_times[:26]):
        packet = np.ascontiguousarray(ep.imu_window(i), np.float64)
        assert lib.step(float(t), np.ascontiguousarray(images[i]), packet, len(packet), prefix[i]) == 0
    log = next((OUT / 'public-n2-218-knownrot_a_replace-parity-repair-trace' / archive.stem / 'report/logs').glob('*/estimate.tum'))
    wasm = np.loadtxt(log)
    return {'episode': archive.stem, 'native_opencv': version, 'wasm_opencv': '4.12.0',
            'reset_causal_prefix_exact': bool(np.array_equal(prefix, native_rows[:26])),
            'first_camera_pose_exact': bool(np.array_equal(native_rows[0, :7], [0, 0, 0, 0, 0, 0, 1])),
            'max_position_delta_m': float(np.linalg.norm(native_rows[:, :3]-wasm[:, 1:4], axis=1).max()),
            'final_position_delta_m': float(np.linalg.norm(native_rows[-1, :3]-wasm[-1, 1:4]))}


def main():
    archives = sorted(Path('/data/backups/rganapa/Sebastian/tmp/viobench-public-replay').glob('*/*.zip'))
    with concurrent.futures.ProcessPoolExecutor(4) as pool:
        rows = list(pool.map(one, archives))
    result = {'python_wasm': rows, 'native_wasm': native(archives[0]),
              'note': 'Numerical acceptance parity is measured, never inferred from aggregate ATE.'}
    target = ROOT / 'results/eval/fusion-completion/parity-audit.json'
    target.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
