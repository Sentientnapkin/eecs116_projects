"""Actual Wasm replay; direct unaligned RMSE, historical hold-last and upstream-origin fill.

Use PYTHONPATH pointing to the pinned upstream VIOBench checkout. No Sim(3) is computed.
"""
import argparse
import dataclasses
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.datasets.episode import FrameSequence
from viobench.tools.runner.engine import Engine, WASMTIME_VERSION
from viobench.tools.runner.sandbox import Sandbox, SandboxError


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def replay(wasm, archive, crop, count, output, metadata=None):
    archive_hash = digest(archive)
    if metadata and metadata.get('parent_sha256'):
        assert archive_hash == metadata['parent_sha256'], str(archive)
    original = read_episode(archive)
    first = int(np.searchsorted(original.frame_times, original.frame_times[0] + crop - 1e-8))
    count = min(count or original.num_frames, original.num_frames - first)
    frames = FrameSequence(lambda i: original.frames[first+i], count, original.frames.frame_shape)
    episode = dataclasses.replace(original, frames=frames, frame_times=original.frame_times[first:first+count])
    engine = Engine()
    output.mkdir(parents=True, exist_ok=True)
    states = np.full((count,13), np.nan)
    fuel = np.zeros(count, dtype=np.int64)
    failure = None
    attempted = 0
    init_fuel = 0
    try:
        guest = Sandbox(wasm, engine, log_dir=output)
        config, images = episode.adapt(guest.resolution)
        guest.init(config)
        init_fuel = guest.init_fuel
        for i, (t,image,imu) in enumerate(episode.steps(images)):
            attempted = i+1
            try:
                result = guest.step(t,image,imu)
            except SandboxError as exc:
                fuel[i] = exc.fuel
                raise
            states[i] = np.r_[result.pose,result.twist]
            fuel[i] = result.fuel
    except SandboxError as exc:
        failure = str(exc)
    valid = np.isfinite(states).all(axis=1) & np.any(states[:,3:7] != 0,axis=1)
    held = np.zeros((count,3))
    previous = np.zeros(3)
    for i in range(count):
        if valid[i]:
            previous = states[i,:3]
        held[i] = previous
    origin = np.where(valid[:,None],states[:,:3],0.)
    truth = episode.ground_truth_relative()[:,:3]
    twist = episode.ground_truth_twist()
    omega_body = twist[0,3:] @ episode.T_body_camera[:3,:3].T
    velocity_body = twist[0,:3] @ episode.T_body_camera[:3,:3].T - np.cross(omega_body,episode.T_body_camera[:3,3])
    squared = np.sum((held-truth)**2,axis=1)
    text = (output/'stdout.txt').read_text() if (output/'stdout.txt').exists() else ''
    initialized = re.findall(r'openvins: initialized at t=([0-9.eE+-]+)',text)
    row = dict(metadata or {}, archive=str(archive), archive_sha256=archive_hash, crop_s=crop,
               frames=count, duration_s=float(episode.frame_times[-1]-episode.frame_times[0]),
               completed=failure is None, failure=failure, filled_frames=int((~valid).sum()),
               frames_attempted=attempted, unaligned_ate_m=float(np.sqrt(squared.mean())),
               upstream_origin_ate_m=float(np.sqrt(np.mean(np.sum((origin-truth)**2,axis=1)))),
               initialization_times_absolute_s=[float(t) for t in initialized],
               initialization_times_since_first_frame_s=[float(t)-float(episode.frame_times[0]) for t in initialized],
               init_fuel=init_fuel, peak_fuel_per_frame=int(fuel.max(initial=0)),
               start_speed_mps=float(np.linalg.norm(velocity_body)),
               start_camera_speed_mps=float(np.linalg.norm(twist[0,:3])),
               prefixes={str(n):dict(frames=n,unaligned_ate_m=float(np.sqrt(squared[:n].mean())),
                                      filled_frames=int((~valid[:n]).sum()),peak_fuel_per_frame=int(fuel[:n].max(initial=0)))
                         for n in (600,601,1200) if n<=count},
               wasm_sha256=digest(wasm),wasmtime=WASMTIME_VERSION,
               scoring='mean Euclidean position squared, sqrt per flight; hold last usable pose; origin before first; no alignment')
    row['mean_unaligned_ate_m']=row['unaligned_ate_m']
    relative_times=episode.frame_times-episode.frame_times[0]
    row['prefix_ate_m']={str(s):float(np.sqrt(squared[relative_times<s-1e-8].mean()))
                         for s in (30,60) if relative_times[-1]>=s-.051}
    row['prefix_frames']={str(n):float(np.sqrt(squared[:n].mean())) for n in (600,601,1200) if n<=count}
    row['metered_wasm']=True
    np.savez_compressed(output/'trajectory.npz',states=states,truth_position=truth,fuel=fuel,times=episode.frame_times)
    (output/'result.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row),flush=True)
    return row


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('wasm',type=Path)
    parser.add_argument('archive',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--crop',type=float,default=0)
    parser.add_argument('--frames',type=int)
    args=parser.parse_args()
    replay(args.wasm,args.archive,args.crop,args.frames,args.output)
