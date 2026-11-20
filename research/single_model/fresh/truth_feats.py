"""Per fresh flight: start speed, angle(true start velocity, camera axis), detector inputs (frame-0 IMU window)."""
import json, sys, glob, os
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, '.')
from research.guard_fusion import traj as T
POOL = '/data/backups/rganapa/Sebastian/tmp/fresh_pool'

def one(ep):
    t, s, meta = T.load_truth(POOL, ep)
    from viobench.tools.datasets.storage import read_episode
    e = read_episode(f'{POOL}/{ep}.zip', frames='none')
    Rbc = np.asarray(e.T_body_camera)[:3, :3]   # camera -> body (T_body_camera)
    axis = np.array([0., 0., 1.])               # truth states are in the CAMERA frame (verified vs IMU): optical axis = +z
    n = int(np.sum(t - t[0] <= 0.5 + 1e-9))
    v = s[:n, 7:10].mean(0)                     # camera-frame velocity
    sp = float(np.linalg.norm(v))
    ang = float(np.degrees(np.arccos(np.clip(v @ axis / max(sp, 1e-9), -1, 1)))) if sp > 1e-6 else None
    w = np.asarray(e.imu_window(0))
    f = float(np.linalg.norm(w[:, 1:4].mean(0))); g = float(np.linalg.norm(w[:, 4:7].mean(0)))
    return dict(episode=ep, speed0=sp, angle=ang, det_f=f, det_g=g, det_moving=bool(f > 8.8 or g > 0.2), q0=s[0, 3:7].tolist(), v0_body=v.tolist())

if __name__ == '__main__':
    eps = sorted(os.path.basename(p)[:-4] for p in glob.glob(POOL + '/*.zip'))
    with Pool(16) as p:
        rows = p.map(one, eps)
    json.dump(rows, open('research/single_model/fresh/truth_feats.json', 'w'))
    print(len(rows))
