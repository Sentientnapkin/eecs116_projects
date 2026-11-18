"""Causal hand-built optical-flow features on the versioned orientation cache."""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

from common import Flight
from pairs import build, digest
from pathlib import Path
from uuid import uuid4

BASE = 5
GX, GY = 12, 9


def grid(w, h):
    xs = (np.arange(GX) + 0.5) * w / GX
    ys = (np.arange(GY) + 0.5) * h / GY
    X, Y = np.meshgrid(xs, ys)
    return np.stack([X.ravel(), Y.ravel()], 1).astype(np.float32)


def extract(path):
    parent_cache = build(path)
    key = digest(__file__)[:16] + "-" + parent_cache.name
    out = Path("data/feat-causal") / key
    if out.exists():
        return out
    f = Flight(path)
    H, W = f.frames.shape[1:]
    fx, fy, cx, cy = f.K["fx"], f.K["fy"], f.K["cx"], f.K["cy"]
    Kc = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])
    Kinv = np.linalg.inv(Kc)
    R_bc = f.T_bc[:3, :3]
    with np.load(parent_cache) as data:
        Rg, imu = data["R"], data["imu"]
    P0 = grid(W, H)
    flow = np.zeros((f.F, GX * GY * 2 + 6), np.float32)
    lk = dict(winSize=(15, 15), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.01))
    for k in range(BASE, f.F):
        a, b = f.frames[k - BASE], f.frames[k]
        # camera rotation from frame k-BASE to k (camera axes): R_c = R_bc^T R_b(a)^T R_b(b) R_bc maps cam_b -> cam_a
        R_ab = R_bc.T @ Rg[k - BASE].T @ Rg[k] @ R_bc
        Hrot = Kc @ R_ab.T @ Kinv  # pixel in a -> where it would be in b under pure rotation
        pred = cv2.perspectiveTransform(P0[None], Hrot)[0]
        P1, st, _ = cv2.calcOpticalFlowPyrLK(a, b, P0, pred.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW, **lk)
        if P1 is None or st is None:
            continue
        ok = st.ravel() == 1
        tr = np.zeros((GX * GY, 2), np.float32)
        d = (P1 - pred)
        d[:, 0] /= fx; d[:, 1] /= fy
        tr[ok] = d[ok]
        mag = np.linalg.norm(tr[ok], axis=1) if ok.any() else np.zeros(1)
        flow[k, :GX * GY * 2] = tr.ravel()
        flow[k, GX * GY * 2:] = [*np.quantile(mag, [0.1, 0.25, 0.5, 0.75, 0.9]), ok.mean()]
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(f".{uuid4().hex}.npz")
    np.savez_compressed(temp, imu=imu, flow=flow, v_body=f.v_body.astype(np.float32),
                        tier=f.tier, scene=f.scene, fov=f.fov, parent_cache=parent_cache.name)
    os.replace(temp, out)
    return out


if __name__ == "__main__":
    import glob
    paths = sorted(glob.glob(sys.argv[1]))
    with ProcessPoolExecutor(6) as ex:
        for i, p in enumerate(ex.map(extract, paths)):
            if i % 25 == 0:
                print(i, p, flush=True)
