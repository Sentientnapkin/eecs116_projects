"""ana2.py EVALDIR POOLDIR FLIGHT frames.. : pos err, vel err (cam axes), rot err (deg), speed est/gt"""
import sys
from pathlib import Path
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.geometry import quaternion_to_matrix
ev, pool, fid = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]; F = [int(x) for x in sys.argv[4:]]
d = sorted(ev.glob(f'**/{fid}/report/logs/*/estimate.tum'))[0]
ep = read_episode(pool / (fid + '.zip'), frames='none'); gt = ep.ground_truth_state(); est = load_estimates(d, ep.frame_times)
for f in F:
    Re = quaternion_to_matrix(est[f, 3:7]); Rg = quaternion_to_matrix(gt[f, 3:7])
    dR = Re.T @ Rg; ang = np.degrees(np.arccos(np.clip((np.trace(dR) - 1) / 2, -1, 1)))
    # tilt error: angle between gravity directions = compare Re^T g0 vs Rg^T g0 with g0 = gt camera-0 frame gravity unknown -> use Rg col
    print(f, 'pos %.2f' % np.linalg.norm(est[f, :3] - gt[f, :3]), 'vel %.2f' % np.linalg.norm(est[f, 7:10] - gt[f, 7:10]), 'rot %.1f' % ang,
          'spd %.2f/%.2f' % (np.linalg.norm(est[f, 7:10]), np.linalg.norm(gt[f, 7:10])))
