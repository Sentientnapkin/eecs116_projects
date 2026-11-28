"""Cache IMU windows + truth (camera-0 frame) for every episode zip: out_dir/<name>.npz. Usage: cache_imu.py OUT ZIP..."""
import sys, os, numpy as np
from multiprocessing import Pool
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import interpolate_poses, poses_to_matrices
OUT = sys.argv[1]
def one(path):
    name = os.path.basename(path)[:-4]; dst = f"{OUT}/{name}.npz"
    if os.path.exists(dst): return name, "skip"
    try:
        ep = read_episode(path, frames="lazy")
        t = ep.frame_times; F = len(t)
        imu = np.stack([ep.imu_window(i) for i in range(1, F)])  # (F-1,10,7)
        tr = ep.ground_truth
        M = poses_to_matrices(interpolate_poses(tr[:, 0], tr[:, 1:8], t))
        Tbc = ep.T_body_camera; Rbc, tbc = Tbc[:3, :3], Tbc[:3, 3]
        Rwb, pwb = M[:, :3, :3], M[:, :3, 3]
        pc = pwb + np.einsum("nij,j->ni", Rwb, tbc); Rwc = Rwb @ Rbc
        cam = (pc - pc[0]) @ Rwc[0]                      # camera centres in camera-0 axes
        Rc0c = np.einsum("ji,njk->nik", Rwc[0], Rwc)     # camera k orientation in camera 0
        np.savez(dst, t=t, imu=imu, cam=cam, Rc0c=Rc0c, Tbc=Tbc, Rwb0=Rwb[0])
        return name, "ok"
    except Exception as e:
        return name, f"ERR {e}"
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    with Pool(12) as p:
        for n, s in p.imap_unordered(one, sys.argv[2:]): 
            if s != "skip": print(n, s, flush=True)
