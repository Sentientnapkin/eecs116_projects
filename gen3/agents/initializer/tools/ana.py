"""ana.py EVALDIR POOLDIR [frames..]: per flight position error |p_est - p_gt| and camera-velocity error at given frames, plus ATE."""
import sys, glob
from pathlib import Path
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
ev, pool = Path(sys.argv[1]), Path(sys.argv[2]); F = [int(x) for x in sys.argv[3:]] or [20, 40, 60, 100, 200, 600, 1199]
print('flight', 'ATE', ' '.join(f'p{f}' for f in F), ' '.join(f'v{f}' for f in F))
for d in sorted(ev.glob('*/*/report/logs/*/estimate.tum')) or sorted(ev.glob('*/report/logs/*/estimate.tum')):
    fid = [p for p in d.parts if p.startswith('s3')][0]
    if not (pool / (fid + '.zip')).exists(): continue
    ep = read_episode(pool / (fid + '.zip'), frames='none')
    gt = ep.ground_truth_state(); est = load_estimates(d, ep.frame_times)
    e = np.linalg.norm(est[:, :3] - gt[:, :3], axis=1); ve = np.linalg.norm(est[:, 7:10] - gt[:, 7:10], axis=1)
    ate = np.sqrt(np.nanmean(e ** 2))
    print(fid, f'{ate:.2f}', ' '.join(f'{e[min(f, len(e) - 1)]:.2f}' for f in F), ' '.join(f'{ve[min(f, len(e) - 1)]:.2f}' for f in F))
