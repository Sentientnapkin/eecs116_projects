"""Why is a flight's error large? Splits the C solution's error into speed and heading parts, per flight.

  ATE        graded error            zeros    error of "never moved"
  path       estimated path length / true path length (>1: thinks it flew farther)
  far        farthest estimated distance from start / true farthest
  flow       median camera speed / true speed, while truly moving
  rescaled   ATE if the whole estimate were scaled by the best single factor (speed fixed, heading kept)
  rotfix     ATE if the estimate were rotated by the best single rotation (heading fixed, speed kept)
  late       ATE over the second half only
"""
import ctypes
import os
import sys

import numpy as np

from csolution import CSolution
from viobench.tools.datasets.sources import episodes
from viobench.tools.runner.metrics import evaluate_trajectory

LIB = None
for a in list(sys.argv[1:]):
    if a.startswith("lib="):
        LIB = a[4:]
        sys.argv.remove(a)


def ate(gt, positions):
    return float(np.sqrt(np.mean(np.sum((positions - gt) ** 2, axis=1))))


rows = []
for episode in episodes(sys.argv[1:]):
    gt = episode.ground_truth_state()
    config, frames = episode.adapt((320, 240))
    kwargs = {"library": LIB} if LIB else {}
    solver = CSolution(config, **kwargs)
    est, flow, scale = [], [], []
    has_scale = hasattr(solver.lib, "debug_speed_scale")
    if has_scale:
        solver.lib.debug_speed_scale.restype = ctypes.c_double
    for t, f, imu in episode.steps(frames):
        est.append(solver.step(float(t), f, imu))
        flow.append(solver.lib.debug_flow_speed())
        scale.append(solver.lib.debug_speed_scale() if has_scale else 1.0)
    est, flow, scale = np.array(est), np.array(flow), np.array(scale)
    cache = os.path.expanduser(f"~/ws_proto/cache/{os.path.basename(LIB or 'libvio_host.so')[:-3]}")
    os.makedirs(cache, exist_ok=True)
    np.savez(f"{cache}/{episode.name}_{str(episode.hash)[:6]}.npz",
             est=est, gt=gt, flow=flow, scale=scale, t=episode.frame_times, windows=solver.windows())
    p, q = est[:, :3], gt[:, :3]
    m = evaluate_trajectory(gt, est, episode.frame_times)
    true_speed = np.linalg.norm(gt[:, 7:10], axis=1)
    moving = true_speed > 0.1
    path = np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)) / np.sum(np.linalg.norm(np.diff(q, axis=0), axis=1))
    far = np.linalg.norm(p, axis=1).max() / max(np.linalg.norm(q, axis=1).max(), 1e-6)
    good = moving & (flow > 0)
    flow_ratio = np.median(flow[good] / true_speed[good]) if good.any() else float("nan")
    s = np.sum(p * q) / max(np.sum(p * p), 1e-9)
    rescaled = ate(q, p * max(s, 0))
    U, _, Vt = np.linalg.svd(q.T @ p)  # best rotation (no scale) mapping the estimate onto the truth
    R = U @ np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]) @ Vt
    best = ate(q, p @ R.T)
    half = len(p) // 2
    late = ate(q[half:], p[half:])
    zeros = ate(q, np.zeros_like(q))
    rows.append((m.ate_rmse, zeros))
    print(f"{episode.name[:30]:30s} ATE {m.ate_rmse:5.2f} zeros {zeros:5.2f} | path {path:4.2f} far {far:4.2f} flow {flow_ratio:4.2f}"
          f" | rescaled {rescaled:5.2f} (x{s:4.2f}) rotfix {best:5.2f} | late {late:5.2f} rot {np.degrees(m.rotation_rmse):4.0f}deg"
          f" | accel scale {np.median(scale[len(scale) // 2:]):4.2f}",
          flush=True)
print(f"\nMEAN ATE {np.mean([r[0] for r in rows]):.2f}  zeros {np.mean([r[1] for r in rows]):.2f}")
