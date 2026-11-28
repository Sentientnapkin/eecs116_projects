"""Turn viobench-stage3 shard tars (320x240 gray frames + IMU + ground truth) into
  ~/data/imucache/<SET>/<id>.npz   (same layout as cache_imu.py), and
  ~/data/viscache/<SET>/<id>.npz   (vis3.features_for: direction d (3), flow magnitude q, valid points; per frame 1..N-1)

    python3 shard_prep.py SET TAR [TAR ...]        (WSL ~/.venv: needs viobench + cv2; ~/data/load_shards.py)
Only v3, 1200-frame flights. The camera mount is the viobench default (identical in every flight checked).
"""
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.expanduser("~/data"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TBC = np.array([[0, 0, 1, 0], [-1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 0, 1.0]])
SET = sys.argv[1]
IMU_DIR = os.path.expanduser(f"~/data/imucache/{SET}"); VIS_DIR = os.path.expanduser(f"~/data/viscache/{SET}")


def cache_arrays(f):
    from viobench.tools.geometry import interpolate_poses, poses_to_matrices
    t = f["frame_times"]; imu = f["imu"]; F = len(t)
    win = []
    for i in range(1, F):
        rows = imu[(imu[:, 0] > t[i - 1] + 1e-9) & (imu[:, 0] <= t[i] + 1e-9)]
        if len(rows) != 10:
            raise ValueError(f"frame {i}: {len(rows)} IMU rows")
        win.append(rows)
    tr = f["gt"]
    M = poses_to_matrices(interpolate_poses(tr[:, 0], tr[:, 1:8], t))
    Rbc, tbc = TBC[:3, :3], TBC[:3, 3]
    Rwb, pwb = M[:, :3, :3], M[:, :3, 3]
    pc = pwb + np.einsum("nij,j->ni", Rwb, tbc); Rwc = Rwb @ Rbc
    cam = (pc - pc[0]) @ Rwc[0]
    Rc0c = np.einsum("ji,njk->nik", Rwc[0], Rwc)
    return dict(t=t, imu=np.stack(win), cam=cam, Rc0c=Rc0c, Tbc=TBC, Rwb0=Rwb[0])


def one_tar(tar):
    import fit_cheap as fc
    import load_shards as L
    import vis3
    done = 0
    for f in L.flights(tar):
        if f.get("roster_version") != 3 or len(f["frame_times"]) != 1200:
            continue
        dst = os.path.join(IMU_DIR, f["id"] + ".npz"); vdst = os.path.join(VIS_DIR, f["id"] + ".npz")
        if os.path.exists(dst) and os.path.exists(vdst):
            continue
        try:
            c = cache_arrays(f)
            np.savez(dst, **c)
            R, _ = fc.prep(c)
            fx = 160.0 / np.tan(np.radians(f["fov_deg"]) / 2)
            K = np.array([[fx, 0, 159.5], [0, fx, 119.5], [0, 0, 1]])
            V = vis3.features_for(f["frames"].astype(np.float64), R, K)
            np.savez(vdst, vis=V, fov=f["fov_deg"], cls=f["setting_class"])
            done += 1
        except Exception as e:
            print(f"ERR {f['id']}: {e}", flush=True)
    return f"{os.path.basename(tar)}: {done}"


if __name__ == "__main__":
    os.makedirs(IMU_DIR, exist_ok=True); os.makedirs(VIS_DIR, exist_ok=True)
    with Pool(int(os.environ.get("PROCS", 4))) as p:
        for msg in p.imap_unordered(one_tar, sys.argv[2:]):
            print(msg, flush=True)
