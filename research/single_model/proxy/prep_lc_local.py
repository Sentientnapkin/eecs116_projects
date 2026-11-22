"""Startup-net cache (same format and C-matched pipeline as learned_c/prep2.py) from any episode zips. vio_eval python.

  vio_eval/Scripts/python prep_lc_local.py --zips <dir or glob> [...] --workers 6
Per flight -> work/lc_cache/<stem>.npz with, for phases 0 and 2: anchors a = p + 5k, gray128 frames at anchors
(320x240 INTER_AREA -> mean of 3 channels -> exact 2.5x area -> round), raw-gyro rotation and specific-force integrals at
the anchors, 50 ms window means, true body velocity at the anchors; K at 128x96, T_bc, fx at 320.
"""
import argparse, glob, os, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np

CACHE = Path("C:/Users/alexa/vio_data/work/lc_cache")
PHASES = (0, 2)


def area_matrix(n_out, n_in):
    s = n_in / n_out; W = np.zeros((n_out, n_in), np.float32)
    for i in range(n_out):
        lo, hi = i * s, (i + 1) * s
        for j in range(int(np.floor(lo)), min(n_in, int(np.ceil(hi)))):
            W[i, j] = (min(hi, j + 1) - max(lo, j)) / s
    return W


WX, WY = area_matrix(128, 320), area_matrix(96, 240)


def exp_rot(w):
    th = np.linalg.norm(w, axis=1, keepdims=True); k = w / np.maximum(th, 1e-12); th = th[:, :, None]
    K = np.zeros((len(w), 3, 3)); K[:, 0, 1], K[:, 0, 2], K[:, 1, 2] = -k[:, 2], k[:, 1], -k[:, 0]
    K[:, 1, 0], K[:, 2, 0], K[:, 2, 1] = k[:, 2], -k[:, 1], k[:, 0]
    return np.eye(3)[None] + np.sin(th) * K + (1 - np.cos(th)) * (K @ K)


def gray128(f640):
    import cv2
    f = cv2.resize(np.asarray(f640), (320, 240), interpolation=cv2.INTER_AREA)
    g = f.astype(np.float32).mean(2)
    return np.clip(np.floor(WY @ g @ WX.T + 0.5), 0, 255).astype(np.uint8)


def one(zpath):
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.geometry import poses_to_matrices, interpolate_poses
    z = Path(zpath); out = CACHE / f"{z.stem}.npz"
    if out.exists():
        return z.stem, "cached"
    ep = read_episode(str(z), frames="lazy")
    N = ep.num_frames; t = ep.frame_times; gt = ep.ground_truth; h = 0.005
    tt = np.stack([np.maximum(t - h, gt[0, 0]), t, np.minimum(t + h, gt[-1, 0])])
    Tb = np.stack([poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], x)) for x in tt])
    vw = (Tb[2, :, :3, 3] - Tb[0, :, :3, 3]) / (tt[2] - tt[0])[:, None]
    vb_all = np.einsum("nji,nj->ni", Tb[1, :, :3, :3], vw)
    imu = ep.imu; ti, a_b, w_b = imu[:, 0], imu[:, 1:4], imu[:, 4:7]
    dt = np.diff(ti, prepend=ti[0] - 0.005)
    dR = exp_rot(w_b * dt[:, None]); Rc = np.empty_like(dR); cur = np.eye(3)
    for i in range(len(dR)):
        cur = cur @ dR[i]; Rc[i] = cur
    Vc = np.cumsum(np.einsum("nij,nj->ni", Rc, a_b) * dt[:, None], 0)
    cam = ep.config["camera"]; s = 128 / ep.resolution[0]
    d = {}
    for p in PHASES:
        anchors = np.arange(p, N, 5)
        fr = np.stack([gray128(ep.frames[int(j)]) for j in anchors])
        idx_end = np.searchsorted(ti, t[anchors] + 1e-6, side="right") - 1
        idx_start = np.searchsorted(ti, t[anchors] - 0.05 + 1e-6, side="right")
        fm = np.zeros((len(anchors), 3)); gm = np.zeros((len(anchors), 3))
        for a in range(len(anchors)):
            lo, hi = idx_start[a], idx_end[a] + 1
            fm[a] = a_b[lo:hi].mean(0); gm[a] = w_b[lo:hi].mean(0)
        d.update({f"frames{p}": fr, f"Rcum{p}": Rc[idx_end].astype(np.float32), f"Vint{p}": Vc[idx_end].astype(np.float32),
                  f"fmean{p}": fm.astype(np.float32), f"gmean{p}": gm.astype(np.float32), f"vb{p}": vb_all[anchors].astype(np.float32)})
    K = np.array([cam["fx"] * s, cam["fy"] * s, (cam["cx"] + .5) * s - .5, (cam["cy"] + .5) * s - .5])
    tmp = out.with_suffix(".tmp.npz")
    np.savez(tmp, K=K, Tbc=ep.T_body_camera, fx320=np.float64(cam["fx"] * 0.5), **d)
    os.replace(tmp, out)
    return z.stem, "ok"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--zips", nargs="+", required=True); ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    files = []
    for g in a.zips:
        files += sorted(glob.glob(os.path.join(g, "*.zip"))) if os.path.isdir(g) else sorted(glob.glob(g))
    print(len(files), "flights", flush=True); t0 = time.time()
    with Pool(a.workers) as p:
        for i, (n, s) in enumerate(p.imap_unordered(one, files)):
            if i % 20 == 0:
                print(i, n, s, f"{time.time() - t0:.0f}s", flush=True)
