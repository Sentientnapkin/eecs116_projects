"""Compare an actual shortened guest replay with the emitted full-replay prefix."""
import json
from pathlib import Path
import sys

import numpy as np
import wasm_eval as we
from viobench.tools.datasets.episode import Episode

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results/loop/fusion-completion'


def main():
    source = next(Path('/data/backups/rganapa/Sebastian/tmp/viobench-public-replay').glob('sim-ProcTHOR-Train-1-0000/*.zip'))
    full = we.read_episode(source, frames='memory')
    n = 600
    config = json.loads(json.dumps(full.config))
    config['episode']['num_frames'] = n
    config['episode']['name'] += '-prefix600'
    capped = Episode(name=config['episode']['name'], config=config, frame_times=full.frame_times[:n],
        frames=np.asarray(full.frames)[:n], imu=full.imu[full.imu[:, 0] <= full.frame_times[n-1]+1e-8],
        ground_truth=full.ground_truth[full.ground_truth[:, 0] <= full.frame_times[n-1]+0.02],
        T_body_camera=full.T_body_camera, meta={k:v for k,v in full.meta.items() if k not in ('hash','path')})
    capped.check_consistency()
    archive = OUT / 'stage-prefix600.zip';we.write_episode(capped, archive)
    reread = we.read_episode(archive, frames='none')
    packets_exact = all(np.array_equal(full.imu_window(i), reread.imu_window(i)) for i in range(n))
    wasm = Path('/data/backups/rganapa/Sebastian/baselines/fuel/art/kf-k2-staged2r/odometry.wasm')
    short_out = OUT / 'staged6r-causal-prefix'
    we.run_one(wasm, archive, short_out)
    short_log = next((short_out/archive.stem/'report/logs').glob('*/estimate.tum'))
    full_log = next(Path('/data/backups/rganapa/Sebastian/baselines/fuel/runs/public-kf-k2-staged2r').glob('sim-ProcTHOR-Train-1-0000/report/logs/*/estimate.tum'))
    short_rows, full_rows = np.loadtxt(short_log), np.loadtxt(full_log)[:n]
    short_twist, full_twist = np.loadtxt(short_log.parent/'twist.txt'), np.loadtxt(full_log.parent/'twist.txt')[:n]
    result = {'frames': n, 'wasm_sha256': we.sha256(wasm), 'source_archive_sha256': we.sha256(source),
        'short_archive_sha256': we.sha256(archive), 'first_timestamp_s': float(short_rows[0,0]),
        'same_timestamps_and_packets': packets_exact and bool(np.array_equal(full.frame_times[:n], reread.frame_times)),
        'emitted_pose_prefix_exact': bool(np.array_equal(short_rows, full_rows)),
        'emitted_twist_prefix_exact': bool(np.array_equal(short_twist, full_twist)),
        'first_camera_pose_exact': bool(np.array_equal(short_rows[0,1:8], [0,0,0,0,0,0,1])),
        'max_pose_component_delta': float(np.max(np.abs(short_rows-full_rows))),
        'rule': 'No reset at30s; two independently initialized actual guest replays of identical received prefix.'}
    (ROOT/'results/eval/fusion-completion/staged-causal-prefix.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
