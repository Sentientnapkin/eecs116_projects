"""Matched raw learned guest replay; truth is used only after inference for scoring."""
import argparse
import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import sys

import numpy as np

DEPLOY = Path('/data/backups/rganapa/Sebastian/eecs116_projects/.claude/worktrees/agent-ad6636639c9915912/research')
sys.path.insert(0, str(DEPLOY / 'native_odometry'))
from replay import Host
from common import Flight
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.engine import Engine
from viobench.tools.runner.sandbox import Sandbox, SandboxError


def run(task):
    import cv2
    cv2.setNumThreads(1)
    archive, build, out, crop, metered, metadata = task
    archive, build, out = map(Path, (archive, build, out))
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / 'result.json'
    artifact_hash = hashlib.sha256((build/'odometry.wasm').read_bytes()).hexdigest()
    with archive.open('rb') as handle:
        archive_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
    if metadata.get('parent_sha256') and archive_hash != metadata['parent_sha256']:
        raise ValueError(f'Archive hash mismatch: {archive}')
    if result_path.exists():
        old = json.loads(result_path.read_text())
        if (old.get('wasm_sha256'), old.get('archive_sha256'), old.get('crop_s'), old.get('metered_wasm')) == (artifact_hash, archive_hash, crop, metered):
            return old
    ep = read_episode(archive)
    first = int(np.searchsorted(ep.frame_times, ep.frame_times[0] + crop - 1e-8))
    camera, frames = ep.adapt((320, 240))
    host = Host(build)
    host.init(camera)
    guest = Sandbox(build / 'odometry.wasm', Engine(), log_dir=out) if metered else None
    if guest:
        guest.init(camera)
    outputs, fuel, delta, failure = [], [], 0., None
    for i in range(first, ep.num_frames):
        image = np.ascontiguousarray(frames[i])
        imu = np.ascontiguousarray(ep.imu_window(i), dtype=np.float64)
        state = np.empty(13, dtype=np.float64)
        if host.lib.step(ep.frame_times[i], image, imu, len(imu), state):
            raise RuntimeError(f'Host failed {archive} {i}')
        if guest:
            try:
                step = guest.step(ep.frame_times[i], image, imu)
            except SandboxError as exc:
                failure = str(exc)
                fuel.append(exc.fuel)
                break
            wasm_state = np.r_[step.pose, step.twist]
            delta = max(delta, float(np.max(np.abs(state - wasm_state))))
            fuel.append(step.fuel)
            state = wasm_state
        outputs.append(state.copy())
    attempted = len(outputs) + int(failure is not None)
    filled = ep.num_frames-first-len(outputs)
    if filled:
        previous = outputs[-1].copy() if outputs else np.r_[np.zeros(6), 1., np.zeros(6)]
        outputs.extend([previous.copy() for _ in range(filled)])
    states = np.stack(outputs)
    # Scoring uses a fresh reset origin at the selected camera frame.
    truth = Flight(archive, crop=crop).cam_gt
    errors = np.sum((states[:, :3] - truth) ** 2, axis=1)
    times = ep.frame_times[first:] - ep.frame_times[first]
    prefixes = {str(s): float(np.sqrt(errors[times < s - 1e-8].mean()))
                for s in (30, 60) if times[-1] >= s - .051}
    result = dict(archive=str(archive), archive_sha256=archive_hash, crop_s=crop, **metadata,
                  frames=len(states), completed=failure is None, failure=failure, filled_frames=filled,
                  frames_attempted=attempted,
                  mean_unaligned_ate_m=float(np.sqrt(errors.mean())),
                  prefix_ate_m=prefixes, duration_s=float(times[-1]),
                  peak_fuel_per_frame=max(fuel) if fuel else None,
                  init_fuel=guest.init_fuel if guest else None,
                  host_wasm_state_max_delta=delta if guest else None,
                  prefix_frames={str(n):float(np.sqrt(errors[:n].mean())) for n in (600,601,1200) if n<=len(states)},
                  start_speed_mps=float(np.linalg.norm(Flight(archive,crop=crop).v_body[0])),
                  wasm_sha256=artifact_hash,
                  metered_wasm=bool(guest))
    np.savez_compressed(out/'trajectory.npz', states=states, truth=truth, times=times,
                        fuel=np.asarray(fuel))
    result_path.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('build', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--set', choices=['public', 'campaign-dev'], required=True)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--metered', action='store_true')
    args = p.parse_args()
    tasks = []
    if args.set == 'public':
        base = Path('/data/backups/rganapa/Sebastian/tmp/viobench-public-replay')
        for archive in sorted(base.glob('sim-*/*.zip')):
            tasks.append((str(archive), str(args.build), str(args.output/archive.stem), 0., args.metered,
                          dict(catalog='procthor', scene='ProcTHOR-Train-1')))
        assert len(tasks) == 10
    else:
        manifest = Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/data/native-campaign/dev-records.json')
        for r in json.loads(manifest.read_text())['records']:
            assert r['split'] == 'dev'
            archive = Path('/data/backups/rganapa/Sebastian/gen/raw/dev')/(r['flight_id']+'.zip')
            tasks.append((str(archive), str(args.build), str(args.output/(r['flight_id']+'-'+str(r['crop_s']))),
                          r['crop_s'], args.metered, {k:r[k] for k in ['catalog', 'scene', 'regime', 'parent_sha256']}))
        assert len(tasks) == 120
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(run, tasks))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(dict(rows=rows,
        mean_unaligned_ate_m=float(np.mean([r['mean_unaligned_ate_m'] for r in rows]))),indent=2)+'\n')


if __name__ == '__main__':
    main()
