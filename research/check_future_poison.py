"""Fresh-process determinism, prefix, and future-sensor poisoning check for any ABI guest.

Fixtures are sensor-only NPZ files from make_sensor_fixture.py. No truth is read.
Corruption starts strictly AFTER each tested prefix, including the associated IMU
packets. Each replay is a new process and a fresh sandbox. A failing suffix may
terminate, but every prefix row must have been emitted and match bit for bit.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np


def replay(wasm, fixture, output, mode, prefix, seed):
    from viobench.tools.runner.sandbox import Sandbox
    with np.load(fixture, allow_pickle=False) as f:
        camera = json.loads(str(f['camera_json']))
        times = f['absolute_times'].copy()
        offsets = f['packet_offsets'].copy()
        frames = f['frames'].copy()
        packets = f['packets'].copy()
    if not 0 < prefix < len(times):
        raise ValueError(f'prefix {prefix} needs a nonempty future in fixture with {len(times)} frames')
    rng = np.random.default_rng(seed)
    if mode == 'poison':
        frames[prefix:] = rng.integers(0, 256, size=frames[prefix:].shape, dtype=np.uint8)
        # Keep packet times valid; corrupt all future acceleration/angular-rate values.
        suffix = packets[offsets[prefix]:, 1:]
        suffix[:] = rng.normal(0, 100, size=suffix.shape)
    n = prefix if mode == 'prefix' else len(times)
    guest = Sandbox(wasm, log_dir=output.parent / (output.stem + '-logs'))
    guest.init(camera)
    states, failure = [], None
    for i in range(n):
        packet = packets[offsets[i]:offsets[i+1]].copy()
        packet[:, 0] += times[0]
        try:
            row = guest.step(float(times[i]), frames[i], packet)
            states.append(np.r_[row.pose, row.twist])
        except Exception as exc:
            failure = f'{type(exc).__name__}: {exc}'
            break
    np.savez(output, states=np.asarray(states).reshape(-1, 13), failure=np.asarray(failure or ''))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wasm', required=True, type=Path)
    p.add_argument('--fixture', action='append', required=True, type=Path)
    p.add_argument('--prefix', action='append', type=int)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--seed', default=217, type=int)
    p.add_argument('--worker-mode', choices=('full', 'prefix', 'poison'), help=argparse.SUPPRESS)
    a = p.parse_args()
    prefixes = a.prefix or [600, 1200]
    if a.worker_mode:
        replay(a.wasm, a.fixture[0], a.output, a.worker_mode, prefixes[0], a.seed)
        return
    a.output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for j, fixture in enumerate(a.fixture):
        for k in prefixes:
            paths = {}
            def one(mode):
                output = a.output.parent / f'{a.output.stem}-{j}-{k}-{mode}.npz'
                subprocess.run([sys.executable, str(Path(__file__).resolve()), '--wasm', str(a.wasm),
                                '--fixture', str(fixture), '--output', str(output), '--prefix', str(k),
                                '--worker-mode', 'full' if mode == 'repeat' else mode,
                                '--seed', str(a.seed)], check=True, env=os.environ.copy())
                with np.load(output, allow_pickle=False) as f:
                    return mode, (f['states'].copy(), str(f['failure']))
            with ThreadPoolExecutor(max_workers=4) as pool:
                paths = dict(pool.map(one, ('full', 'repeat', 'prefix', 'poison')))
            full = paths['full'][0]
            checks = {mode: bool(len(full) >= k and len(paths[mode][0]) >= k and
                                  np.array_equal(full[:k], paths[mode][0][:k]))
                      for mode in ('repeat', 'prefix', 'poison')}
            checks['repeat'] = bool(paths['full'][1] == paths['repeat'][1] and
                                    np.array_equal(full, paths['repeat'][0]) and len(full) >= k)
            row = {'fixture': str(fixture), 'prefix_frames': k, 'checks': checks,
                   'failures': {m: v[1] or None for m, v in paths.items()},
                   'poisoned_frames': 'indices >= prefix_frames', 'pass': all(checks.values())}
            results.append(row)
            print(json.dumps(row), flush=True)
    report = {'wasm': str(a.wasm), 'sha256': hashlib.sha256(a.wasm.read_bytes()).hexdigest(),
              'results': results, 'pass': all(r['pass'] for r in results)}
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    if not report['pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
