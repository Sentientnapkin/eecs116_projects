"""Distribution of truth max/RMS distance from start (3-D, horizontal, vertical) and speed stats on pool flights. Analysis only."""
import json, os, glob, sys
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from research.guard_fusion import traj as T
from viobench.tools.datasets.storage import read_episode
DIRS = {'fresh': '/data/backups/rganapa/Sebastian/tmp/fresh_pool', 'holdout': '/data/backups/rganapa/Sebastian/gen/raw-holdout/final'}
def one(a):
    d, ep = a
    t, s, meta = T.load_truth(d, ep)
    e = read_episode(f'{d}/{ep}.zip', frames='none')
    Rbc = np.asarray(e.T_body_camera)[:3, :3]
    w = np.asarray(e.imu_window(0)); f = w[:, 1:4].mean(0)
    up = Rbc.T @ (f / np.linalg.norm(f))
    p = s[:, :3] - s[0, :3]; v = s[:, 7:10]
    dist = np.linalg.norm(p, axis=1); vert = p @ up; hor = np.linalg.norm(p - np.outer(vert, up), axis=1)
    sp = np.linalg.norm(v, axis=1); path = float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))
    # speed over sliding 1 s windows (path rate)
    dt = float(np.median(np.diff(t))); n1 = max(1, int(round(1.0 / dt)))
    pr = np.linalg.norm(p[n1:] - p[:-n1], axis=1) / (n1 * dt) if len(p) > n1 else np.zeros(1)
    def rate(w):
        n=max(1,int(round(w/dt)))
        return float((np.linalg.norm(p[n:]-p[:-n],axis=1)/(n*dt)).max()) if len(p)>n else 0.0
    return dict(ep=ep,maxpr2=rate(2.0),maxpr3=rate(3.0),maxpr5=rate(5.0), src=d.split('/')[-1] if False else None, maxd=float(dist.max()), rmsd=float(np.sqrt((dist**2).mean())), maxh=float(hor.max()), maxv=float(np.abs(vert).max()),
                rmsv=float(np.sqrt((vert**2).mean())), maxsp=float(sp.max()), p99sp=float(np.percentile(sp, 99)), meansp=float(sp.mean()), maxpr1=float(pr.max()), path=path, dur=float(t[-1] - t[0]))
if __name__ == '__main__':
    out = {}
    with Pool(12) as pool:
        for k, d in DIRS.items():
            eps = sorted(os.path.basename(p)[:-4] for p in glob.glob(d + '/*.zip'))
            out[k] = pool.map(one, [(d, e) for e in eps])
    json.dump(out, open('research/single_model/tailcap/truth_extent.json', 'w'))
    for k, rows in out.items():
        print(k, len(rows))
        for f in ('maxd', 'rmsd', 'maxh', 'maxv', 'rmsv', 'maxsp', 'p99sp', 'meansp', 'maxpr1', 'maxpr2', 'maxpr3', 'maxpr5', 'path', 'dur'):
            v = np.array([r[f] for r in rows]); print(f'  {f:7s} mean {v.mean():6.2f} p50 {np.percentile(v,50):6.2f} p90 {np.percentile(v,90):6.2f} p99 {np.percentile(v,99):6.2f} max {v.max():6.2f}')
