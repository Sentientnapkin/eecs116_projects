"""Compare each vision window's rotation correction with the true one (from ground truth). Diagnostic only."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "solution"))
import solution as S  # noqa: E402
from viobench.tools.datasets.sources import episodes  # noqa: E402
from viobench.tools.geometry import poses_to_matrices  # noqa: E402


def log_so3(R):
    angle = np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if angle < 1e-9:
        return np.zeros(3)
    return angle / (2 * np.sin(angle)) * np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])


episode = next(episodes(sys.argv[1:]))
gt = episode.ground_truth_state()
T = poses_to_matrices(gt[:, :7])
config, frames = episode.adapt((320, 240))
S.Solution.OPTIONS = dict(vision=True, rot_apply=0.0, bias_gain=0.0)  # measure only, change nothing
solver = S.Solution(config)
records = []
original_start, original_finish = solver._start_window, solver._finish_window


def start(gray, t):
    original_start(gray, t)
    if solver.window is not None:
        solver.window["index"] = solver.frame_index


def finish(t):
    w = solver.window
    f0, f1 = solver._bearings(w["start_pixels"]), solver._bearings(w["pixels"])
    R_pred = solver.R_ci @ w["R_wb"].T @ solver.R_wb @ solver.R_ic
    d_rot, res = S.solve_rotation_only(f0, f1, R_pred)
    t_imu = solver.R_ci @ w["R_wb"].T @ (solver.p - w["p"])
    d_epi, t_cam, _ = S.solve_epipolar(f0, f1, R_pred, t_imu if np.linalg.norm(t_imu) > 1e-3 else np.array([0, 0, 1.0]))
    i0, i1 = w["index"], solver.frame_index
    R_true = T[i0, :3, :3].T @ T[i1, :3, :3]  # camera k1 in camera k0
    d_true = log_so3(R_pred.T @ R_true)      # R_true = R_pred exp(d_true)
    rel = T[i0, :3, :3].T @ (T[i1, :3, 3] - T[i0, :3, 3])
    t_true = rel / max(np.linalg.norm(rel), 1e-9)
    records.append((i0, i1, len(f0), np.median(res), d_true, d_rot, d_epi, t_true, t_cam))
    original_finish(t)


solver._start_window, solver._finish_window = start, finish
for index, (t, frame, imu) in enumerate(episode.steps(frames)):
    solver.step(float(t), frame, imu)
    if len(records) >= 60:
        break

print("frames    pts  parallax |  true error (mrad)       | rotation-only fit     | epipolar fit          | t_true . t_est")
for i0, i1, n, par, dt, dr, de, tt, te in records:
    fmt = lambda v: " ".join(f"{1000 * x:6.1f}" for x in v)
    print(f"{i0:4d}-{i1:4d} {n:3d}  {1000 * par:6.1f}  | {fmt(dt)} | {fmt(dr)} | {fmt(de)} | {tt @ te:+.2f}")
moving = np.array([tt @ te for _, _, _, par, _, _, _, tt, te in records if par > 0.008])
print(f"moving windows: {len(moving)}, direction within 30 deg: {np.mean(moving > 0.866):.0%}, "
      f"backwards: {np.mean(moving < 0):.0%}")
