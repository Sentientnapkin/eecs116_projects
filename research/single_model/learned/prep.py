"""Cache per-flight start-window data for the learned startup-velocity net.

For every flight kept by the split rules (see split.py) writes <cache>/<name>.npz with
  frames  (A,96,128) uint8 gray, area-downsampled from the stored 640x480, at frame indices 0,5,10,... (A anchors)
  vb      (N,3) body(IMU)-frame velocity from central differences of the ground truth (TRUTH: targets only)
  up      (N,3) body-frame up vector (truth, only for analysis)
  Rcum    (A,3,3) gyro-integrated body orientation (raw gyro, no bias removal), world = body orientation at the first IMU row
  Vint    (A,3)   integral of R_t a_t dt (specific force in the integration frame) up to the anchor frame time
  fmean, gmean (A,3) mean specific force / gyro over the IMU window (t_j-0.05, t_j] (what imu_window(j) delivers)
  K (4,)  fx,fy,cx,cy at 128x96 ; Tbc (4,4)
Run: python -B prep.py [--workers 40] [--only val|train|sel]  (teacher venv).  Never opens fold-4 archives.
"""
import argparse, json, os, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
sys.path.insert(0, str(Path(__file__).parent))
import split

CACHE = Path('/data/backups/rganapa/Sebastian/tmp/learned_cache')
RAW = split.RAW


def exp_rot(w):
    th = np.linalg.norm(w, axis=1)
    k = np.where(th > 1e-9, 1.0 / np.maximum(th, 1e-12), 0.0)
    a = w * k[:, None]
    c, s = np.cos(th), np.sin(th)
    out = np.zeros((len(w), 3, 3))
    for i in range(len(w)):
        x = a[i]
        Kx = np.array([[0, -x[2], x[1]], [x[2], 0, -x[0]], [-x[1], x[0], 0]])
        out[i] = np.eye(3) + s[i] * Kx + (1 - c[i]) * (Kx @ Kx) if th[i] > 1e-9 else np.eye(3) + np.array([[0, -w[i, 2], w[i, 1]], [w[i, 2], 0, -w[i, 0]], [-w[i, 1], w[i, 0], 0]])
    return out


def one(name):
    out = CACHE / f'{name}.npz'
    if out.exists():
        return name, 'cached'
    import cv2
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.geometry import poses_to_matrices, interpolate_poses
    ep = read_episode(RAW / f'{name}.zip', frames='lazy')
    N = ep.num_frames
    anchors = np.arange(0, N, 5)
    fr = np.empty((len(anchors), 96, 128), np.uint8)
    for a, j in enumerate(anchors):
        f = ep.frames[int(j)]
        g = f.astype(np.float32).mean(2) if f.ndim == 3 else f.astype(np.float32)
        fr[a] = np.clip(cv2.resize(g, (128, 96), interpolation=cv2.INTER_AREA) + 0.5, 0, 255).astype(np.uint8)
    gt = ep.ground_truth
    h = 0.005
    t = ep.frame_times
    tt = np.stack([np.maximum(t - h, gt[0, 0]), t, np.minimum(t + h, gt[-1, 0])])
    Tb = np.stack([poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], x)) for x in tt])
    vw = (Tb[2, :, :3, 3] - Tb[0, :, :3, 3]) / (tt[2] - tt[0])[:, None]
    Rwb = Tb[1, :, :3, :3]
    vb = np.einsum('nji,nj->ni', Rwb, vw)
    up = Rwb[:, 2, :]  # R^T z = row 2
    imu = ep.imu
    ti, a_b, w_b = imu[:, 0], imu[:, 1:4], imu[:, 4:7]
    dt = np.diff(ti, prepend=ti[0] - 0.005)
    dR = exp_rot(w_b * dt[:, None])
    Rc = np.empty_like(dR); cur = np.eye(3)
    for i in range(len(dR)):
        cur = cur @ dR[i]; Rc[i] = cur
    inc = np.einsum('nij,nj->ni', Rc, a_b) * dt[:, None]
    Vc = np.cumsum(inc, 0)
    idx_end = np.searchsorted(ti, t[anchors] + 1e-6, side='right') - 1
    idx_start = np.searchsorted(ti, t[anchors] - 0.05 + 1e-6, side='right')
    fmean = np.zeros((len(anchors), 3)); gmean = np.zeros((len(anchors), 3))
    for a in range(len(anchors)):
        lo, hi = idx_start[a], idx_end[a] + 1
        fmean[a] = a_b[lo:hi].mean(0); gmean[a] = w_b[lo:hi].mean(0)
    cam = ep.config['camera']; s = 128 / ep.resolution[0]
    K = np.array([cam['fx'] * s, cam['fy'] * s, (cam['cx'] + .5) * s - .5, (cam['cy'] + .5) * s - .5])
    np.savez(out.with_suffix('.tmp.npz'), frames=fr, vb=vb.astype(np.float32), up=up.astype(np.float32),
             Rcum=Rc[idx_end].astype(np.float32), Vint=Vc[idx_end].astype(np.float32), fmean=fmean.astype(np.float32),
             gmean=gmean.astype(np.float32), K=K, Tbc=ep.T_body_camera, times=t.astype(np.float64),
             fx320=np.float64(cam['fx'] * 0.5))
    os.replace(out.with_suffix('.tmp.npz'), out)
    return name, 'ok'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=40)
    ap.add_argument('--only', default='all')
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = split.load_rows()
    names = [r['name'] for r in rows if r['role'] in (('train', 'val', 'search_sel') if a.only == 'all' else (a.only,))]
    print(len(names), 'flights', flush=True)
    t0 = time.time()
    with Pool(a.workers) as p:
        for i, (n, s) in enumerate(p.imap_unordered(one, names)):
            if i % 25 == 0:
                print(i, n, s, f'{time.time()-t0:.0f}s', flush=True)
