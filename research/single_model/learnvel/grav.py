"""gravity labels: per cached flight, unit gravity direction in BODY frame at anchor frames (phases 0, 2): gb{p} = R_wb^T (0,0,-1).
  grav.py ZIPDIR [workers] -> tmp/lv_grav/<name>.npz (only for zips whose name is in a cache: lc_cache / lv_cache_train / lv_cache)"""
import sys, os
from pathlib import Path
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
OUT = Path('/data/backups/rganapa/Sebastian/tmp/lv_grav')
def label(zp):
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.geometry import poses_to_matrices, interpolate_poses
    zp = Path(zp); out = OUT / f'{zp.stem}.npz'
    if out.exists(): return zp.stem, 'cached'
    ep = read_episode(zp, frames='none'); t = ep.frame_times; gt = ep.ground_truth; N = len(t)
    Tb = poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], t))
    g = np.einsum('nji,j->ni', Tb[:, :3, :3], np.array([0, 0, -1.0]))
    d = {f'gb{p}': g[np.arange(p, N, 5)].astype(np.float32) for p in (0, 2)}
    OUT.mkdir(parents=True, exist_ok=True); np.savez(out.with_suffix('.tmp.npz'), **d); os.replace(out.with_suffix('.tmp.npz'), out)
    return zp.stem, 'ok'
if __name__ == '__main__':
    from multiprocessing import Pool
    zs = [z for z in sorted(Path(sys.argv[1]).glob('*.zip'))]
    with Pool(int(sys.argv[2]) if len(sys.argv) > 2 else 16) as p:
        r = p.map(label, zs)
    print(len(r), sum(x[1] == 'ok' for x in r))
