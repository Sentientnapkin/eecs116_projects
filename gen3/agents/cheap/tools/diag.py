"""diag.py POOL FLIGHT NAME [NAME..]: position / camera-velocity error over time for each eval NAME (gen3/evals/NAME/*/) + its stderr tail."""
import sys, glob
from pathlib import Path
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
G = Path('/data/backups/rganapa/Sebastian/gen3/evals'); pool, fid = Path(sys.argv[1]), sys.argv[2]
F = [5, 10, 15, 20, 30, 40, 60, 100, 200, 400, 800, 1199]
ep = read_episode(pool / (fid + '.zip'), frames='none'); gt = ep.ground_truth_state()
print('frames', F)
print('gt |v|  ', ' '.join(f'{np.linalg.norm(gt[f, 7:10]):5.2f}' for f in F))
for name in sys.argv[3:]:
    ds = sorted(glob.glob(str(G / name / '*' / '*' / fid / 'report/logs/*/estimate.tum')), key=lambda p: Path(p).stat().st_mtime)
    if not ds: print(name, 'missing'); continue
    d = Path(ds[-1]).parent; est = load_estimates(d / 'estimate.tum', ep.frame_times)
    e = np.linalg.norm(est[:, :3] - gt[:, :3], axis=1); ve = np.linalg.norm(est[:, 7:10] - gt[:, 7:10], axis=1)
    def qm(q):
        x, y, z, w = q.T; return np.stack([1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), 2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w), 2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)], 1).reshape(-1, 3, 3)
    Re, Rg = qm(est[:, 3:7]), qm(gt[:, 3:7]); D = np.einsum('nji,njk->nik', Re, Rg); ang = np.degrees(np.arccos(np.clip((np.trace(D, axis1=1, axis2=2) - 1) / 2, -1, 1)))
    print(f'{name:24s} ATE {np.sqrt(np.nanmean(e**2)):.2f}'); print('  pos err', ' '.join(f'{e[f]:5.2f}' for f in F)); print('  rot deg', ' '.join(f'{ang[f]:5.1f}' for f in F)); print('  vel err', ' '.join(f'{ve[f]:5.2f}' for f in F))
    se = (d / 'stderr.txt').read_text().split('\n') if (d / 'stderr.txt').exists() else []
    if se and len(sys.argv) > 3: print('\n'.join('    ' + l for l in se[:40]))
